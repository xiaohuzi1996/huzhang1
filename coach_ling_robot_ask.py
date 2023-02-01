# -*- coding: utf-8 -*-
# @Time  :2022/1/17 18:55
# @File  :main.py
import logging
import numpy as np
from flask import request, Blueprint
from cache.redis_base_cache import RedisCache
from jump_rule.redis_data import RedisData
from jump_rule.jump_node import configuration_flag
from jump_rule.normal_jump_rule import normal_flag
from models.model_predict import ModelPredictModel
from jump_rule.dialogue_management import phone_total_score
import time
redis_cache_instance = RedisCache()
# 每次重运行之前，清空redis内存,使用r.keys(i)找到要删除的键，然后使用r.delete(i)，循环删除i的键值对
for i in ['robot_node', 'robot_talk', 'collector_talk', 'sql_node', 'configuration_data', 'configuration_node']:
    redis_cache_instance.cache_clean_mark(mark=i)

ns = Blueprint('coach_ling_robot_ask', __name__, url_prefix='/ai_api')
import pdb
pdb.set_trace()

pm = ModelPredictModel()
# 传入相似度pm模型，得到每句话的向量（目前方案用文本分类不合理）
redis_data_instance = RedisData(redis_cache_instance, pm)


@ns.route('/coach_ling_robot', methods=['POST'])
def coach_ling_robot_api():
    flag = request.json.get("flag", "")  # 是否使用前段跳转节点逻辑
    scene_flag = request.json.get("scene_flag", "")  # 场景模块标签 0是内测 1是广发。。。。
    exam_flag = request.json.get("exam_flag", "train")  # 是否考试标志
    train_id = str(request.json.get("train_id", ""))  # 每一通对话的用户id,字符串格式
    is_end = request.json.get("is_end", "")  # 是否结束跳转，非空是结束，空是未结束/
    base_data = request.json.get("base_data", "")  # 数据集合['text' 'current_node' 'duration']  duration--时长
    fill_variable = request.json.get("fill_variable", "")  # 催收员话术替换变量
    logging.info('----测试receive：----：' + 'flag:' + str(flag) + '; scene_flag:' + str(scene_flag) +
                 '; is_end:' + str(is_end) + '; base_data:' + str(base_data) +
                 '; fill_variable:' + str(fill_variable) + '; train_id:' + str(train_id))
    import pdb
    pdb.set_trace()
    last_dict = main_ling(str(flag), scene_flag, exam_flag, train_id, is_end, base_data, fill_variable, redis_cache_instance,
                          redis_data_instance)
    return last_dict


@ns.route('/coach_ling_robot/refresh_configuration_data', methods=['get'])
def refresh_configuration_data():
    global redis_data_instance
    global redis_cache_instance
    try:
        redis_cache_instance.cache_clean_mark(mark='configuration_data')
        redis_data_instance = RedisData(redis_cache_instance, pm)
        dic = {'status': 'succeed', 'msg': 'The configuration rules have been updated'}
        logging.info('The configuration rules update succeeded')
    except Exception as e:
        dic = {'status': 'failed', 'msg': e}
        logging.info('The configuration rules update failure')
    return dic


def main_ling(flag, scene_flag, exam_flag, train_id, is_end, base_data, fill_variable, redis_cache, redis_data):
    """
    :param flag:        是否使用前段跳转节点逻辑
    :param scene_flag:  场景模块标签 0是内测 1是广发
    :param exam_flag:   是否考试标志
    :param train_id:    每一通对话的用户id
    :param is_end:      是否结束跳转，非空是结束，空是未结束
    :param base_data:   数据集合['text' 'current_node' 'duration']  duration--时长
    :param fill_variable:   催收员话术替换变量
    :param redis_cache  实例化 redis
    :param redis_data   reids 数据
    :return: 返回全部数据
    """
    # 结束对话 进行打分
    script_library_id = int(scene_flag)  # 将场景id赋值给话术库id
    if is_end:
        if scene_flag == 0:
            # 结束对话
            status, dic_robot_redis = redis_cache.cache_get(mark=redis_data.robot_mutex, key=str(train_id))
            if status is True:
                dic_robot_redis = eval(dic_robot_redis.decode())
                if set(dic_robot_redis['lis_score']) == {-1}:
                    phone_score_dict = {
                        'phone_total_score': 0,
                        'phone_speed_score': 0,
                        'phone_point_score': 0,
                        'phone_sem_score': 0,
                        "phone_fluency_score": 0,
                        "phone_banned_words_score": 0,
                    }
                    detail_msg = {
                        "key_words": f"{sum(dic_robot_redis['lis_node_point'])}/{sum(dic_robot_redis['lis_all_node_point'])}",
                        "speed": "0",
                        "similarity": "0",
                        "key_words_text": f"本次对话命中关键词0个，参考回复实例中的标准话术可以命中更多关键词哦",
                        "speed_text": "本次对话语速为0字/分钟,可以适当提高语速哦",
                        "similarity_text": "本次对话综合话术相似度0%,模仿回复示例中的话术可以提高话术相似度哦",
                    }
                    phone_last_dict = {'msg': 'success', 'phone_score_dict': phone_score_dict, 'detail_msg': detail_msg}
                    logging.info('----return：----：' + str(phone_last_dict))
                    return phone_last_dict
                else:
                    # dic_robot_redis = eval(dic_robot_redis.decode())
                    phone_score_dict = phone_total_score(dic_robot_redis)
                    # 相似度总分
                    simi_score = np.mean(dic_robot_redis['lis_similarity'])
                    if simi_score > 90:
                        similarity_text = f"本次对话综合话术相似度{simi_score:.2f}%,已经很棒啦!"
                    else:
                        similarity_text = f"本次对话综合话术相似度{simi_score:.2f}%,模仿回复示例中的话术可以提高话术相似度哦"

                    # 语速总分
                    sentence_speed_avg = np.mean(dic_robot_redis['sentence_speed'])
                    if sentence_speed_avg < 300:
                        speed_text = f"本次对话语速为{sentence_speed_avg:.2f}字/分钟,可以适当提高语速哦"
                    elif sentence_speed_avg > 380:
                        speed_text = f"本次对话语速为{sentence_speed_avg:.2f}字/分钟,可以适当降低语速哦"
                    else:
                        speed_text = f"本次对话语速为{int(sentence_speed_avg)}字/分钟,已经很棒啦!"

                    detail_msg = {
                        "key_words": f"{sum(dic_robot_redis['lis_node_point'])}/{sum(dic_robot_redis['lis_all_node_point'])}",
                        "speed": f"{int(np.mean(dic_robot_redis['sentence_speed']))}",
                        "similarity": f"{np.mean(dic_robot_redis['lis_similarity']):.2f}%",
                        "key_words_text": f"本次对话命中关键词{sum(dic_robot_redis['lis_node_point'])}个，参考回复实例中的标准话术可以命中更多关键词哦",
                        "speed_text": speed_text,
                        "similarity_text": similarity_text,
                    }

                    # redis_cache.cache_clean(mark=redis_data.robot_mutex, key=str(train_id))
                    phone_last_dict = {'msg': 'success', 'phone_score_dict': phone_score_dict, 'detail_msg': detail_msg}
                    logging.info('----return：----：' + str(phone_last_dict))
                    return phone_last_dict
            else:
                return {'msg': 'failed', 'detail_msg': 'The train_id is empty'}

        else:  # 配置文件 结束打分
            status, dic_robot_redis = redis_cache.cache_get(mark=redis_data.configuration_node,
                                                            key=f'{script_library_id}-{train_id}')
            if status:
                dic_robot_redis = eval(dic_robot_redis.decode())
                # 未进行实质性对话，辱骂结束
                if set(dic_robot_redis['lis_score']) == {-1}:
                    phone_score_dict = {
                        'phone_total_score': 0,
                        'phone_speed_score': 0,
                        'phone_point_score': 0,
                        'phone_sem_score': 0,
                        "phone_fluency_score": 0,
                        "phone_banned_words_score": 0,
                    }
                    detail_msg = {
                        "key_words": f"{sum(dic_robot_redis['lis_node_point'])}/{sum(dic_robot_redis['lis_all_node_point'])}",
                        "speed": "0",
                        "similarity": "0",
                        "key_words_text": f"本次对话命中关键词0个，参考回复实例中的标准话术可以命中更多关键词哦",
                        "speed_text": "本次对话语速为0字/分钟,可以适当提高语速哦",
                        "similarity_text": "本次对话综合话术相似度0%,模仿回复示例中的话术可以提高话术相似度哦",
                    }
                    phone_last_dict = {'msg': 'success', 'phone_score_dict': phone_score_dict, 'detail_msg': detail_msg}
                    logging.info('----return：----：' + str(phone_last_dict))
                    return phone_last_dict
                else:
                    phone_score_dict = phone_total_score(dic_robot_redis)
                    # 相似度总分
                    simi_score = np.mean(dic_robot_redis['lis_similarity'])
                    if simi_score > 90:
                        similarity_text = f"本次对话综合话术相似度{simi_score:.2f}%,已经很棒啦!"
                    else:
                        similarity_text = f"本次对话综合话术相似度{simi_score:.2f}%,模仿回复示例中的话术可以提高话术相似度哦"

                    # 语速总分
                    sentence_speed_avg = np.mean(dic_robot_redis['sentence_speed'])
                    if sentence_speed_avg < 120:
                        speed_text = f"本次对话语速为{sentence_speed_avg:.2f}字/分钟,可以适当提高语速哦"
                    elif sentence_speed_avg > 330:
                        speed_text = f"本次对话语速为{sentence_speed_avg:.2f}字/分钟,可以适当降低语速哦"
                    else:
                        speed_text = f"本次对话语速为{int(sentence_speed_avg)}字/分钟,已经很棒啦!"

                    detail_msg = {
                        "key_words": f"{sum(dic_robot_redis['lis_node_point'])}/{sum(dic_robot_redis['lis_all_node_point'])}",
                        "speed": f"{int(np.mean(dic_robot_redis['sentence_speed']))}",
                        "similarity": f"{np.mean(dic_robot_redis['lis_similarity']):.2f}%",
                        "key_words_text": f"本次对话命中关键词{sum(dic_robot_redis['lis_node_point'])}个，参考回复实例中的标准话术可以命中更多关键词哦",
                        "speed_text": speed_text,
                        "similarity_text": similarity_text,
                    }

                    # redis_cache.cache_clean(mark=redis_data.robot_mutex, key=str(train_id))
                    phone_last_dict = {'msg': 'success', 'phone_score_dict': phone_score_dict, 'detail_msg': detail_msg}
                    logging.info('----return：----：' + str(phone_last_dict))
                    return phone_last_dict

            else:
                return {'msg': 'failed', 'detail_msg': 'The train_id is empty'}

    # 对话过程中，进行节点跳转
    else:
        # 一般场景,内部培训
        if scene_flag == 0:
            # 一般场景
            if flag == '0':
                start_time = time.time()
                dic_return = normal_flag(exam_flag, train_id, base_data, fill_variable, redis_cache, redis_data)
                logging.info(f'总耗时:{(time.time()-start_time):.4f}')
                logging.info(f'----——flag_0_return：----, {str(dic_return)}')
                return dic_return
        # 配置话术场景
        else:
            dic_return = configuration_flag(
                exam_flag,
                script_library_id,
                train_id,
                base_data,
                fill_variable,
                redis_cache,
                redis_data,
                pm
            )
            logging.info(f'----——configuration_return：---- {str(dic_return)}')
            return dic_return
