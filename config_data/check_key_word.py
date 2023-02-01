# -*- coding: utf-8 -*-
# @Time : 2022/12/2 15:23
import re
import pandas as pd


def fun_1():
    df_node = pd.read_excel('./Node.xlsx', sheet_name=None)
    df_talk = pd.read_excel('./AdviseTalk.xlsx')
    # df_talk = pd.read_excel('./催收员话术库-02.xlsx')

    # 语义点对应的正则
    dic_kind = {}
    for _, line in df_node['text'].iterrows():
        if line['id'] in dic_kind.keys():
            dic_kind[line['id']].append(line['key'])
        else:
            dic_kind[line['id']] = [line['key']]

    dic_node = {}
    for _, line in df_node['node'].iterrows():
        dic_node[line['node_name']] = [int(i) for i in str(line['semantic_point']).split(',')]



    for _, line in df_talk.iterrows():
        node = line['催收员节点']
        text = line['催收员节点话术']
        lis_key = dic_node[node]
        # print(lis_key)

        # lis_key:[11, 19, 6]
        for num in lis_key:
            val = False
            lis_re = dic_kind[num]
            for re_1 in lis_re:
                res = re.search(re_1.replace('、', '|'), text)
                if res:
                    val = True
                    break
            if not val:
                msg = f"文本:{text}   在 语义点 {num}未匹配"
                print(msg)



if __name__ == '__main__':
    fun_1()
