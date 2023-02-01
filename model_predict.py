# -*- coding: utf-8 -*-
# @Time  :2022/2/7 14:31
# @File  :model_predict.py
import tensorflow as tf
import tensorflow.keras as kr
from score_module.semantic_similarity.model import TextCNN
from score_module.semantic_similarity.config import ModelConfig
from score_module.semantic_similarity.data_loader import read_category, read_vocab


class ModelPredictModel:
    def __init__(self):
        tf.compat.v1.reset_default_graph()
        self.config = ModelConfig()
        self.categories, self.cat_to_id, self.id_to_cat = read_category(self.config)
        self.words, self.word_to_id, self.id_to_word = read_vocab(self.config.vocab_path)
        self.config.vocab_size = len(self.words)
        # 下面一行耗时0.4秒
        self.model = TextCNN(self.config)
        # self.session = tf.Session()
        config = tf.compat.v1.ConfigProto(gpu_options=tf.compat.v1.GPUOptions(allow_growth=True))
        self.session = tf.compat.v1.Session(config=config)
        self.session.run(tf.compat.v1.global_variables_initializer())
        saver = tf.compat.v1.train.Saver()
        # model = tf.saved_model.loader.load(self.session, [model_type], self.config.model_pb_path)
        # graph = tf.get_default_graph()
        saver.restore(sess=self.session, save_path=self.config.model_checkpoints_path)


    def predict(self, message):
        # message_nss = self.remove_stop_word(message)
        # 将汉字转换为vocab中对应的id
        data_id = [self.word_to_id[w] for w in message if w in self.word_to_id]
        #import pdb
        #pdb.set_trace()

        feed_dict = {
            self.model.input_x: kr.preprocessing.sequence.pad_sequences([data_id], self.config.max_seq_length),
            self.model.keep_prob: 1
        }

        pred_label = self.session.run([self.model.logits], feed_dict=feed_dict)
        # index, prob = np.argmax(pred_label[0]), max(pred_label[0])
        # print('===========', pred_label[0])
        # return self.id_to_cat[index], pred_label
        return pred_label

    @staticmethod
    def remove_stop_word(message):
        stop_words = []
        message_ns = message.replace('[speaker1]:', '').replace('[speaker2]:', '')
        saved_word_list = list(filter(lambda x: x not in stop_words, list(message_ns)))
        return saved_word_list


if __name__ == '__main__':
    # score_module/semantic_similarity/checkpoints/coach
    msg = "今天天气还挺不错的。"
    message = '胡勇先生放心头条欠款逾期部分块钱现处理现没现没没收入增加收入会时间协商处理东西行关键现逾期天超天话需全额结清现真没说前样话期进现讲什时候处理掉真知道增加收入清楚欠款直样拖现没办法想拖'
    cnn_model = ModelPredictModel()
    res_1 = cnn_model.predict(msg)
    res_2 = cnn_model.predict(message)
    print(type(res_1) ,res_1.shape, res_1)


