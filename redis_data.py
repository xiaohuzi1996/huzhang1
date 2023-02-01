# -*- coding: utf-8 -*-
# @Time  :2022/1/17 19:34
# @File  :redis_data.py
import logging
import random
import pandas as pd
from models.base import session
from cache.get_redis_data import LibraryNode
from collections import defaultdict
import requests
import json
from itertools import chain

headers = {
    'Content-Typ': 'application/json',
    'Content-Length': '<calculated when request is sent>',
    'Host': '<calculated when request is sent>',
    'User-Agent': 'PostmanRuntime/7.26.8',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'content-type': "application/json",
    'cache-control': "no-cache",
}


class RedisData(object):
    """
    获取 redis 存储的数据
    催收员话术表
    机器人话术表
    逻辑跳转表
    """
    def __init__(self, redis, pm):
        # 查询机器人话术
        self.robot_mutex = 'robot_node'
        self.robot_mark = 'robot_talk'
        self.collector_mark = 'collector_talk'
        self.configuration_data = 'configuration_data'
        self.configuration_node = 'configuration_node'
        self.homephone_simiwords = 'homephone_simiwords'  # 同音词
        self.EXPIRE_TIME = 60 * 60 * 24 * 30  # 过期时间设置为一个月
        self.redis = redis
        # 机器人话术表
        self.robot_dic = self.get_robot_dic()
        # 催收员话术表
        self.collector_dic = self.get_advise_dic()
        # 获取节点跳转表
        self.node_jump = self.get_node_jump()
        # 获取容忍度 字典
        self.dic_tolerance = self.get_dic_tolerance()
        # 将 节点跳转数据 传入到redis当中存储
        self.get_configuration_flag_redis()
        self.homephone_words_url = "http://get-homephone-words-svc.ai.svc.cluster.local:9992/ai_api/get_homophone_words"
        self.simiwords_url = "http://get-topk-simiwords-svc.ai.svc.cluster.local:9991/ai_api/get_simi_words"
        # 获取 同音同意词库,(当前作废)
        #self.dic_homephone_similar = self.get_dic_homephone_similar()
        self.pm = pm
        self.advise_vector_text = {}
        self.advise_vector = self.get_advise_vector(pm)
        logging.info('__RedisData()数据初始化完成__')

    def get_robot_dic(self, robot_talk_file='./config_data/RobotTalk.xlsx'):
        """
        获取  机器人回复 话术
        :param robot_talk_file: 机器人话术回复
        :return:
        """
        df = pd.read_excel(robot_talk_file, names=['robot_node', 'robot_text', '_'])
        dic = {}
        for _, line in df.iterrows():
            if line['robot_node'] not in dic.keys():
                dic[line['robot_node']] = [line['robot_text']]
            else:
                dic[line['robot_node']].append(line['robot_text'])
        for key, val in dic.items():
            # set写入redis缓存
            self.redis.cache_join(mark=self.robot_mark, key=key, data=str(val), expire_time=self.EXPIRE_TIME)
        return dic

    def get_advise_dic(self, collector_talk_file='./config_data/AdviseTalk.xlsx'):
        """
        返回 催收员 话语
        :param collector_talk_file:
        :return:
        """
        df = pd.read_excel(collector_talk_file, names=['node', 'text'])
        dic = {}
        for _, line in df.iterrows():
            if line['node'] not in dic.keys():
                dic[line['node']] = [line['text']]
            else:
                dic[line['node']].append(line['text'])
        for key, val in dic.items():
            self.redis.cache_join(mark=self.collector_mark, key=key, data=str(val), expire_time=self.EXPIRE_TIME)
        return dic

    def get_advise_vector(self, pm, collector_talk_file='./config_data/AdviseTalk.xlsx'):
        def replace_symbol(text):
            # res = text.replace("#<debtorName>", "").replace("#<debtorSex>", "").replace("#<productName>", "").replace(
            #     "#<overdueDay>", "").replace("#<overdueMoney>", "").replace("#<servicePhone>", "")
            res = text.replace('#<productName>', '银行金融').replace('#<debtorName>', '李王'). \
                replace('#<debtorSex>', '先生女士').replace('#<overdueDay>', '天月'). \
                replace('#<overdueMoney>', '万块元钱').replace('#<servicePhone>', '1391578') \
                .replace('#<overdueDay>', '天月').replace('#<collectorName>', '委托方'). \
                replace('<overdueDay>', '天月')
            return res
        df = pd.read_excel(collector_talk_file, names=['node', 'text'])
        dic = {}
        for _, line in df.iterrows():
            if line['node'] in dic.keys():
                dic[line['node']].append(pm.predict(replace_symbol(line['text']))[0][0].tolist())
                self.advise_vector_text[line['node']].append(line['text'])
            else:
                dic[line['node']] = [pm.predict(replace_symbol(line['text']))[0][0].tolist()]
                self.advise_vector_text[line['node']] = [line['text']]
        return dic

    def get_node_jump(self, file='./config_data/logical_jump_V5.xlsx'):
        """
        获取节点跳转表逻辑
        :return:
        """
        df = pd.read_excel(file, names=['node', 'next_robot', 'next_node', 'cannot_node', 'mutex_node']).fillna('')
        return df

    def get_exam_jump(self, file='./config_data/logical_jump_V5.xlsx'):
        """
        获取考试节点跳转表逻辑 ,后面更新数据跳转
        :return:
        """
        df = pd.read_excel(file, names=['node', 'next_robot', 'next_node', 'cannot_node', 'mutex_node']).fillna('')
        return df

    def get_dic_tolerance(self):
        tolerance_dic = {'承诺还款-无明确承诺': {'tolerance': 3, 'jump_node': '承诺还款-结束语'},
                         '承诺还款-无明确时间': {'tolerance': 3, 'jump_node': '承诺还款-结束语'},
                         '承诺还款-正在努力': {'tolerance': 3, 'jump_node': '承诺还款-结束语'},
                         '承诺还款-不方便': {'tolerance': 3, 'jump_node': '承诺还款-结束语'},
                         '拒绝还款-骚扰电话': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '拒绝还款-部分还款': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '拒绝还款-直接拒绝': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '拒绝还款-要求延期': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '拒绝还款-近期拖延': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '拒绝还款-长期拖延': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '拒绝还款-资金困难': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '拒绝还款-欠太多': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '拒绝还款-已延期': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '拒绝还款-借不到': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '拒绝还款-其他原因': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '信息核实-利息过高': {'tolerance': 2, 'jump_node': '咨询人工客服-结束语'},
                         '信息核实-产品说明': {'tolerance': 2, 'jump_node': '咨询人工客服-结束语'},
                         '信息核实-还款方式': {'tolerance': 2, 'jump_node': '咨询人工客服-结束语'},
                         '信息核实-电话变动': {'tolerance': 2, 'jump_node': '咨询人工客服-结束语'},
                         '信息核实-欠款信息': {'tolerance': 2, 'jump_node': '咨询人工客服-结束语'},
                         '分期|延期': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '没钱': {'tolerance': 3, 'jump_node': '拒绝还款-结束语'},
                         '其他': {'tolerance': 2, 'jump_node': '拒绝还款-结束语'},
                         '承诺还款': {'tolerance': 2, 'jump_node': '承诺还款-结束语'}}
        return tolerance_dic

    def get_configuration_flag_redis(self):
        val = self.redis.cache_get_by_mark_dic(mark=self.configuration_data)
        if val:
            self.redis.cache_clean_mark(mark=self.configuration_data)
        dic_parent = defaultdict(list)
        dic = {}
        try:
            session_all = session.query(LibraryNode).all()
            for i in session_all:
                dic_sence_id = {'current_id': f'{i.script_library_id}-{i.id}', 'role_type': i.role_type,
                                'script_library_id': i.script_library_id,
                                'node_label': i.node_label, 'standard_script': i.standard_script,
                                'scoring_key_words': i.scoring_key_words, 'point_weights': i.point_weights}
                dic[f'{i.script_library_id}-{i.id}'] = {
                    'parent_node_id': f'{i.script_library_id}-{i.parent_node_id}', 'role_type': i.role_type,
                    'script_library_id': i.script_library_id,
                    'node_label': i.node_label, 'standard_script': i.standard_script,
                    'scoring_key_words': i.scoring_key_words, 'point_weights': i.point_weights}
                dic_parent[f'{i.script_library_id}-{i.parent_node_id}'].append(dic_sence_id)

                if i.parent_node_id == 0:
                    dic[f'{i.script_library_id}-{0}'] = {
                        'parent_node_id': f'0-0', 'role_type': i.role_type,
                        'script_library_id': i.script_library_id,
                        'node_label': i.node_label, 'standard_script': i.standard_script,
                        'scoring_key_words': i.scoring_key_words, 'point_weights': i.point_weights,
                        'next_node': [f'{i.script_library_id}-{i.id}']
                    }
            session.commit()
        except Exception as e:
            session.rollback()
            logging.info(f'redis session error get_configuration_flag_redis , {e}')
            raise
        finally:
            session.close()  # optional, depends on use case
        for key in dic.keys():
            dic[key]['next_node'] = dic_parent[key]
            self.redis.cache_join(self.configuration_data, str(key), str(dic[key]),
                                  expire_time=60 * 60 * 24 * 30)  # 设置失效时间为30天
        logging.info(f'get_configuration_flag_redis 完成存入数据')

    def get_begin_data(self, script_library_id):
        """
        第一次进行对话 返回数据
        :param script_library_id:  int
        :return:
        """
        # logging.info(f'当前对话进程号：{os.getpid()}')
        parent_node_id = f'{script_library_id}-0'
        dic_begin = self.redis.cache_get_wb(mark=self.configuration_data, key=parent_node_id)
        dic_robot = dic_begin['next_node'][0]
        robot_id = dic_robot['current_id']

        dic_collector = self.redis.cache_get_wb(mark=self.configuration_data, key=robot_id)
        lis_collector_choice = random.choice(dic_collector['next_node'])

        return {
            'robot_id': robot_id,
            'robot_talk': dic_begin['standard_script'],
            'robot_node_label': dic_robot['node_label'],
            'collector_id': lis_collector_choice['current_id'],
            'collector_node_label': lis_collector_choice['node_label'],
            'collector_standard_script': lis_collector_choice['standard_script'],
            'val': True
        }

    def get_dic_homephone_similar(self):
        val = self.redis.cache_get_by_mark_dic(mark=self.homephone_simiwords)
        if val:
            self.redis.cache_clean_mark(mark=self.homephone_simiwords)
        dic_homephone_similar = {}
        session_homephone = session.query(LibraryNode).all()
        for i in session_homephone:
            tex_keywords = i.scoring_key_words.replace('；', ';')
            key_score_lis = tex_keywords.split(';')
            key_words_lis = [j.split('-')[0] for j in key_score_lis if j]
            key_words_lis = chain.from_iterable(key_words_lis)
            key_words_lis = list(set(key_words_lis))
            for key_word in key_words_lis:
                if key_word not in dic_homephone_similar.keys():
                    dic_homephone_similar[key_word] = [key_word]
                    try:
                        response_homephone = requests.post(url=self.homephone_words_url,
                                                           data=json.dumps({"word": f"{key_word}"}), headers=headers)
                        response_dic = json.loads(response_homephone.content)
                        lis_res = response_dic.get('homophone_words', [])
                        dic_homephone_similar[key_word].extend(lis_res)

                        response_similar = requests.post(url=self.homephone_words_url,
                                                         data=json.dumps({"word": f"{key_word}"}), headers=headers)
                        response_dic_simi = json.loads(response_similar.content)
                        lis_res_simi = response_dic_simi.get('simi_words', [])
                        dic_homephone_similar[key_word].extend(lis_res_simi)
                    except Exception as e:
                        #pass
                        logging.info(f'{key_word} , 同音同意词数据获取失败 , {e}')
        session.commit()
        self.redis.cache_join(self.homephone_simiwords, str(self.homephone_simiwords),
                              str(dic_homephone_similar),
                              expire_time=60 * 60 * 24 * 30)  # 设置失效时间为30天
        logging.info('homephone_similar_redis 更新数据')
        return dic_homephone_similar
