import redis
import logging
import traceback
from config import REDIS_DB, EXPIRE_TIME

_logger = logging.getLogger()


class BaseCache(object):
    """基础默认的缓存几类"""

    def cache_join(self, mark, key, data, *args, **kwargs):
        """加入缓存"""
        raise NotImplementedError

    def cache_clean(self, mark, key, *args, **kwargs):
        """清除缓存"""
        raise NotImplementedError

    def cache_clean_all(self, mark, *args, **kwargs):
        """清除所有缓存"""
        raise NotImplementedError

    def cache_get(self, mark, key):
        """获取缓存的文件"""
        raise NotImplementedError

    def ping(self):
        """查看缓存是否连通"""
        raise NotImplementedError


class RedisCache(BaseCache):
    """redis的缓存"""
    _instance = None
    # 本地
    # redis_pool = redis.ConnectionPool(host=REDIS_DB.get('host'), port=REDIS_DB.get('port'),db=REDIS_DB.get('db'))
    # 服务端
    redis_pool = redis.ConnectionPool(host=REDIS_DB.get('host'), port=REDIS_DB.get('port'), db=REDIS_DB.get('db'),
                                      password=REDIS_DB.get('password'))

    def __new__(cls, *args, **kwargs):
        """实现缓存对象单例"""
        if cls._instance is None:
            cls._instance = super(RedisCache, cls).__new__(cls)
        return cls._instance

    @staticmethod
    def get_compression_key(mark, key, compression=False):
        if compression:
            return ':'.join([mark, 'compression', key])
        else:
            return ':'.join([mark, key])

    @property
    def redis_connect(self):
        """"""
        return redis.Redis(connection_pool=self.redis_pool)

    def cache_join(self, mark, key, data, compression=False, expire_time=EXPIRE_TIME, **kwargs):
        """
        写入redis缓存
        :param mark: 标记
        :param key: 缓存的标记
        :param data: 缓存的结果
        :param compression: 是否压缩
        :param expire_time: 过期时间
        :return:
        """
        #import pdb
        #pdb.set_trace()
        redis_key = self.get_compression_key(mark, key, compression=compression)
        # keys最好为英文，使用在linux查看redis中文乱码，get（key）会出现得不到键值
        self.redis_connect.set(redis_key, data, ex=expire_time)

    def cache_clean(self, mark, key, *args, **kwargs):
        """
        删除key对应的缓存
        :param mark: 标记
        :param key: 唯一值
        :param args:
        :param kwargs:
        :return:
        """
        redis_key = self.get_compression_key(mark, key)
        self.redis_connect.delete(redis_key)

    def cache_clean_all(self, mark, *args, **kwargs):
        """
        清除所有的标记对应的缓存
        :param mark: 标记分类
        :param args:
        :param kwargs:
        :return:
        """
        pattern = '%s*' % mark
        r = self.redis_connect
        key_list = r.keys(pattern)
        r.delete(key_list)

    def cache_clean_mark(self, mark, *args, **kwargs):
        """
        清除所有的标记对应的缓存
        :param mark: 标记分类
        :param args:
        :param kwargs:
        :return:
        """
        pattern = '%s*' % mark
        r = self.redis_connect
        key_list = r.keys(pattern)
        for i in key_list:
            r.delete(i)

    def cache_get_by_mark(self, mark):
        pattern = '%s*' % mark
        r = self.redis_connect
        key_list = r.keys(pattern)
        phone = []
        for i in range(len(key_list)):
            key = key_list[i]
            one_sentence = r.get(key)
            phone.append(one_sentence.decode())
        return phone

    def cache_get_by_mark_dic(self, mark):
        """
        老王 添加 返回 mark 所有数据
        :param mark:
        :return:
        """
        pattern = '%s*' % mark
        r = self.redis_connect
        key_list = r.keys(pattern)
        phone = []
        for i in range(len(key_list)):
            key = key_list[i]
            one_sentence = r.get(key)
            phone.append({key.decode().split(':')[-1]: eval(one_sentence.decode())})
        return phone

    def cache_get(self, mark, key, compression=False):
        """
        获取缓存的结果
        :param mark: 标记
        :param key: 唯一标识
        :param compression: 是否压缩
        :return:
        """
        try:
            res = self.redis_connect.get(self.get_compression_key(mark, key, compression))
            if res is None:
                return False, None
            else:
                return True, res
        except Exception as e:
            _logger.warning(str(traceback.format_exc()))
            return False, e

    def cache_get_wb(self, mark, key, compression=False):
        """
        获取缓存的结果
        :param mark: 标记
        :param key: 唯一标识
        :param compression: 是否压缩
        :return:
        """
        try:
            res = self.redis_connect.get(self.get_compression_key(mark, key, compression))
            if res is not None:
                return eval(str(res, 'utf-8'))
        except Exception as e:
            _logger.warning(str(traceback.format_exc()))
            return False, e
            # return False, e

    def ping(self):
        """"""
        return self.redis_connect.ping()
