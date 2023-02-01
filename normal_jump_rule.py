# -*- coding: utf-8 -*-
# @Time : 2022/11/7 16:45
import logging
import random
import time
from collections import Counter
from score_module.banned_words_module.banned_words_score import check_banned_words
from score_module.sentence_total_score import sentence_total_score
from score_module.excel_data_dict import node_point_score, semantic_point_id_dict, dic_marked_words, dic_node_to_liwenjing
from score_module.excel_data_dict import df as df_node


def replace_symbol(collector_talk, fill_variable):
    """
    将催收员话术中的 name等信息 进行填充
    :param collector_talk:  催收员话语
    :param fill_variable:   待填充数据
    :return:
    """
    rep_dict = {
        "#<debtorName>": fill_variable['debtor_name'],  # （机器人）欠债人姓名
        "#<debtorSex>": fill_variable['debtor_sex'],  # （机器人）欠债人性别
        "#<productName>": fill_variable['product_name'],  # （催收员） 委托方姓名
        "#<overdueDay>": fill_variable['overdue_day'],  # 逾期时间
        "#<overdueMoney>": fill_variable['overdue_money'],  # 总欠款金额
        "#<servicePhone>": fill_variable['service_phone'],  # 客服热线电话
        "#<collectorName>": fill_variable['collectorName']   # 催收员姓名
    }
    for key, value in rep_dict.items():
        collector_talk = collector_talk.replace(key, value)
    return collector_talk


def query_redis_robot_node(train_id, redis_cache, redis_data, fill_variable):
    """
    根据 train_id ,查询以往的 redis中的  robot 节点 及互斥节点
    如果没有数据，则 在redis当中插入数据
    :return: dict
    """
    status, dic_robot_redis = redis_cache.cache_get(mark=redis_data.robot_mutex, key=str(train_id))
    if status:
        return eval(dic_robot_redis.decode()), False
    else:
        advise_talk = random.choice(redis_cache.cache_get_wb(mark=redis_data.collector_mark, key="身份确认"))
        # 存标准答案 返回替换过的文本
        advise_talk = replace_symbol(advise_talk, fill_variable)
        dic = {
            'lis_robot': ['开场白'],  # 机器人节点
            'lis_mutex': [],  # 互斥后续不可出现节点
            'lis_collector': ['身份确认'],  # 催收员节点
            'lis_advise_talk': [advise_talk],  # 催收员回复话术
            'lis_node_point': [],  # 命中语义点个数
            'lis_all_node_point': [],  # 全部语义点个数
            'lis_similarity': [],  # 相似度得分
            'sentence_speed': [],  # 语速得分
            'lis_score': [],  # 该句总分
            'lis_point_score': [],  # 该句语义点得分
            'lis_fluency': [],
            'lis_banned_words': []
        }
        # 起始节点更新redis
        redis_cache.cache_join(mark=redis_data.robot_mutex, key=str(train_id), data=str(dic))
        return_data = {
            "all_node_dict": {
                "all_robot_node": "开场白",
                "next_node": "身份确认",
            },
            "all_score_dict": {
                "point_score": 0,
                "sem_score_arr": 0,
                "speed_score": 0,
                "fluency_score": 0,
                "total_score": 0,
                "banned_words_score": 0
            },
            "all_talk_dict": {
                "advise_talk": advise_talk,
                "robot_talk_text": "喂，你好",
                "robot_talk_voice": "喂，你好"
            },
            "msg": "success"
        }
        return return_data, True


def get_jump_node(current_node, dic_robot, redis_data, train_id, redis_cache, dic_redis_all_points_num,
                  update_redis=True):
    """
    获取跳转的机器人节点 和 下一时刻对应的催收员节点
    :param current_node: 当前催收员节点
    :param dic_robot:    机器人字典
    :param redis_data:   redis内存数据
    :param train_id:     用户id
    :param redis_cache:  redis
    :param dic_redis_all_points_num:  需要更新到redis 的临时字典
    :param update_redis: 是否更新redis
    :return:
    """
    df = redis_data.node_jump[redis_data.node_jump['node'] == current_node]
    # 机器人可跳转节点列表
    lis_optional = []
    # 机器人互斥节点
    lis_mutex = []

    # 容忍度节点判断,将 容忍度数据 增加到 互斥节点当中
    if dic_robot['lis_robot']:
        # 将过往节点 按照出现过的数量进行排序
        sorted_lis = sorted(Counter(dic_robot['lis_robot']).items(), key=lambda x: x[1], reverse=True)
        for node, count in sorted_lis:
            # 确保该节点在容忍度词典当中  再进行次数判断
            if redis_data.dic_tolerance.get(node, '') and count + 1 >= redis_data.dic_tolerance[node]['tolerance']:
                lis_mutex.append(node)

    # 获取 可跳转节点
    for _, line in df.iterrows():
        robot = line['next_robot']
        if robot not in dic_robot['lis_mutex']:
            lis_optional.append([robot, line['next_node']])

    if not lis_optional:
        logging.info(f'train_id:{train_id}可选项为0，提前结束对话')
        if update_redis:
            dic_robot['lis_robot'].append('END')
            dic_robot['lis_collector'].append('END')
            dic_robot['lis_score'].append(dic_redis_all_points_num['score'])
            redis_cache.cache_join(mark=redis_data.robot_mutex, key=str(train_id), data=str(dic_robot))
        return 'END_BREAK', redis_data.dic_tolerance.get(current_node, {'tolerance': 3, 'jump_node': '拒绝还款-结束语'})[
            'jump_node'], dic_robot
    # 存在多选，随机跳转

    else:
        for _, line in df.iterrows():
            if line['cannot_node']:
                lis_mutex.append(line['cannot_node'])
            if line['mutex_node']:
                lis_mutex.append(line['mutex_node'])
            break

        # 增加概率调节 将生成的列表进行合并
        lis_optional_add = [i for i in lis_optional if "还款" in i] * 4
        lis_optional.extend(lis_optional_add)
        # 增加 身份确认-是的 概率
        lis_optional_add = [i for i in lis_optional if "身份确认-是的" in i] * 10
        lis_optional.extend(lis_optional_add)
        robot_node, collector_node = random.choice(lis_optional)

        if update_redis:
            dic_robot['lis_robot'].append(robot_node)
            # 将 本次产生的节点 也加入到互斥节点当中
            dic_robot['lis_mutex'].extend(list(set(lis_mutex)) + [robot_node])
            dic_robot['lis_collector'].append(collector_node)
            dic_robot['lis_node_point'].append(dic_redis_all_points_num['points_num'])
            dic_robot['lis_all_node_point'].append(dic_redis_all_points_num['all_points_num'])
            dic_robot['lis_similarity'].append(dic_redis_all_points_num['similarity'])
            dic_robot['sentence_speed'].append(dic_redis_all_points_num['sentence_speed'])
            dic_robot['lis_fluency'].append(dic_redis_all_points_num['fluency_score'])
            dic_robot['lis_banned_words'].append(dic_redis_all_points_num['banned_words_score'])
            dic_robot['lis_score'].append(dic_redis_all_points_num['score'])
            dic_robot['lis_point_score'].append(dic_redis_all_points_num['point_score'])
            redis_cache.cache_join(mark=redis_data.robot_mutex, key=str(train_id), data=str(dic_robot))
        return robot_node, collector_node, dic_robot


def normal_flag(exam_flag, train_id, base_data, fill_variable, redis_cache, redis_data):
    # 进行历史机器人节点查询
    dic_redis_robot_node, first_val = query_redis_robot_node(train_id, redis_cache, redis_data, fill_variable)

    # 该id 第一次请求为空，返回 开场白对话
    if first_val is True:
        return dic_redis_robot_node
    else:  # 非第一通对话 ,继续对话
        # 获取 侮辱低俗，回复较短的筛选结果
        check_vulgar_dic = check_banned_words(base_data['text'])
        # 对回复过短进行处理
        if check_vulgar_dic.get('next_node', '') == 'END-拒绝说话过短':
            all_node_dict = {
                "all_robot_node": "温馨提示",
                "next_node": df_node["node"][df_node["node"]["node_name"] == dic_redis_robot_node['lis_collector'][-1]]["liwenjing"].values[0],
            }
            all_talk_dict = {
                "advise_talk": replace_symbol(dic_redis_robot_node['lis_advise_talk'][-1], fill_variable),
                "robot_talk_text": "您的回复过短，无法识别，请重新回答。",
                "robot_talk_voice": "您的回复过短，无法识别，请重新回答。"
            }
            all_score_dict = {
                "total_score": 0,
                "speed_score": 0,
                "point_score": 0,
                "sem_score_arr": 0,
                "fluency_score": 0,
                "banned_words_score": 0
            }
            return {
                "msg": "success",
                "all_node_dict": all_node_dict,
                "all_score_dict": all_score_dict,
                "all_talk_dict": all_talk_dict
            }

        # 辱骂回复
        elif check_vulgar_dic.get('next_node', '') == 'END-拒绝辱骂':
            all_node_dict = {"all_robot_node": "END-拒绝辱骂", "next_node": "END"}
            all_talk_dict = {"advise_talk": "END", "robot_talk_text": "END", "robot_talk_voice": "END"}
            all_score_dict = {
                "total_score": 0,
                "speed_score": 0,
                "point_score": 0,
                "sem_score_arr": 0,
                "fluency_score": 0,
                "banned_words_score": 0
            }
            # 将辱骂信息更新到redis
            dic_redis_robot_node['lis_score'].append(-1)
            # 将辱骂信息更新到 redis
            redis_cache.cache_join(mark=redis_data.robot_mutex, key=str(train_id), data=str(dic_redis_robot_node))
            return {
                "msg": "success",
                "all_node_dict": all_node_dict,
                "all_score_dict": all_score_dict,
                "all_talk_dict": all_talk_dict
            }

        # 正常对话处理
        else:
            # 从redis 获取节点，获取不到的话则赋值默认的开始节点
            current_node = dic_redis_robot_node['lis_collector'][-1]
            # 获取语义总得分，目前的语义得分是三个分值加权平均（节点分数、相似度、语速）
            # 获取下一个跳转节点next_node_msg
            score_dict, detail_message, next_node_msg = sentence_total_score(base_data['text'], current_node,
                                                                             base_data['duration'], redis_data, fill_variable)
            # 相似度 小于60 % 的情况
            # if score_dict.get('sem_score', 0) < 60:
            # 这个改为总得分
            if score_dict.get('total_score', 0) < 60 and exam_flag == "train":
                all_node_dict = {
                    "all_robot_node": "温馨提示",
                    "next_node": dic_node_to_liwenjing.get(current_node, current_node),
                }
                all_talk_dict = {
                    "advise_talk": replace_symbol(dic_redis_robot_node['lis_advise_talk'][-1], fill_variable),
                    "robot_talk_text": "请勿回复与本场景无关的话术！",
                    "robot_talk_voice": "请勿回复与本场景无关的话术！"
                }
                all_score_dict = {
                    "total_score": 0,
                    "speed_score": 0,
                    "point_score": 0,
                    "sem_score_arr": 0,
                    "fluency_score": 0,
                    "banned_words_score": 0
                }
                return {
                    "msg": "success",
                    "all_node_dict": all_node_dict,
                    "all_score_dict": all_score_dict,
                    "all_talk_dict": all_talk_dict
                }
            # 总得分大于 60% 情况
            else:
                total_score = score_dict["total_score"]
                speed_score = score_dict["speed_score"]
                sem_score = score_dict["sem_score"]
                point_score = score_dict["point_score"]
                all_points_num = score_dict["all_points_num"]

                # 获取得分字典
                all_score_dict = {
                    "total_score": int(total_score),
                    "speed_score": int(speed_score),
                    "point_score": int(point_score),
                    "sem_score_arr": int(sem_score),
                    "fluency_score": int(score_dict["fluency_score"]),
                    "banned_words_score": int(score_dict['banned_words_score'])
                }

                # 李文静需求 临时添加更新redis 字典
                dic_redis_all_points_num = {
                    'score': int(total_score),
                    'points_num': len(detail_message['points']),
                    'all_points_num': all_points_num,
                    'similarity': int(sem_score),
                    'sentence_speed': detail_message['sentence_speed'],
                    'point_score': point_score,
                    'vulgar': check_vulgar_dic['semantics_flag'],
                    'fluency_score': score_dict['fluency_score'],
                    "banned_words_score": score_dict['banned_words_score']
                }
                start_time = time.time()
                # 节点跳转  包括redis 存储部分代码  #END-提前结束 拒绝还款-结束语
                robot_node, next_collector_node, dic_redis_robot_node_update = get_jump_node(
                    current_node,
                    dic_redis_robot_node,
                    redis_data,
                    train_id,
                    redis_cache,
                    dic_redis_all_points_num
                )

                # 针对 V2_clear 进行 处理
                if robot_node in ['拒绝还款-部分还款', '拒绝还款-近期拖延', '拒绝还款-要求延期', '拒绝还款-直接拒绝', '拒绝还款-资金困难']:
                    robot_node_break, _, __ = get_jump_node(
                        next_collector_node,
                        dic_redis_robot_node,
                        redis_data, train_id,
                        redis_cache,
                        dic_redis_all_points_num,
                        update_redis=False
                    )
                    if robot_node_break == "END_BREAK":
                        next_collector_node = "拒绝还款-结束语"

                logging.info(f'跳转节点部分耗时:{(time.time() - start_time):.4f}')
                # 老王 修改节点提示  将节点替换成  行为+行为
                if robot_node == 'END_BREAK':
                    robot_node = "END-提前结束"
                    next_node_msg = ['END']
                else:
                    next_node_msg = []
                    point_messages = node_point_score[next_collector_node]
                    arr_points = point_messages.split('|')
                    for point in arr_points:
                        point_id_str, weight_score_str = point.split(',')
                        point_name = semantic_point_id_dict[int(point_id_str)]
                        next_node_msg.append(point_name)

                # 通过节点 获取 机器人话术
                lis_robot_talk = redis_data.robot_dic[robot_node]
                robot_talk = random.choice(lis_robot_talk)

                # 通过节点 获取 催收员话术
                lis_collector_talk = redis_data.collector_dic[next_collector_node]
                collector_talk = random.choice(lis_collector_talk)
                # 替换 名称等占位符
                collector_talk = replace_symbol(collector_talk, fill_variable)
                robot_talk = replace_symbol(robot_talk, fill_variable)

                # 需要新增功能 将产生的催收员话术 更新到redis 当中
                dic_redis_robot_node_update['lis_advise_talk'].append(collector_talk)
                redis_cache.cache_join(mark=redis_data.robot_mutex, key=str(train_id), data=str(dic_redis_robot_node_update))
                all_talk_dict = {
                    "robot_talk_voice": robot_talk,
                    "robot_talk_text": robot_talk.replace('萑', '还'),
                    "advise_talk": collector_talk
                }

                if "+".join(next_node_msg) == "再见结束语":
                    next_node_msg = ['END']

                all_node_dict = {
                    "next_node": dic_marked_words["+".join(next_node_msg)],
                    "all_robot_node": robot_node,
                }

                return {
                    "msg": "success",
                    "all_node_dict": all_node_dict,
                    "all_score_dict": all_score_dict,
                    "all_talk_dict": all_talk_dict,
                }
