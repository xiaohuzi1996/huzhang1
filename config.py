import flask.scaffold
import logging.config
import os
from gunicorn_config import loglevel
flask.helpers._endpoint_from_view_func = flask.scaffold._endpoint_from_view_func


env_dict = os.environ
import pdb
pdb.set_trace()
env = os.environ.get('APP_ENV', 'local')
logging.warning('此次的环境是：    ' + str(env))



if env == 'k8s-staging':
    # 测试环境数据库配置
    MYSQL_URI = env_dict.get("XD_MYSQL", "stagingdb-region.mysql.zhangbei.rds.aliyuncs.com:3306/zichan360_training_robot")
    MYSQL_USER = env_dict.get("XD_MYSQL_USER", "ai_user")
    MYSQL_PW = env_dict.get("XD_MYSQL_PW", "y07a7eGoi1UO")

elif env == 'k8s-prod':
    # 生产环境数据库配置
    MYSQL_URI = env_dict.get("XD_MYSQL", "masterdb.mysql.zhangbei.rds.aliyuncs.com:3306/zichan360_training_robot")
    MYSQL_USER = env_dict.get("XD_MYSQL_USER", "ai_user")
    MYSQL_PW = env_dict.get("XD_MYSQL_PW", "y07a7eGoi1UO")
else:
    # 开发环境数据库配置
    MYSQL_URI = env_dict.get("XD_MYSQL", "stagingdb-region.mysql.zhangbei.rds.aliyuncs.com:3306/zichan360_training_robot")
    MYSQL_USER = env_dict.get("XD_MYSQL_USER", "ai_user")
    MYSQL_PW = env_dict.get("XD_MYSQL_PW", "y07a7eGoi1UO")



# 默认运行环境

# 本地 redis 测试环境
# SYSTEM_ENV = os.environ.get('SYSTEM_ENV_MODULE', 'local')
# 线上 redis  服务环境
SYSTEM_ENV = os.environ.get('SYSTEM_ENV_MODULE', env)


# for sqlalchemy
class Config(object):
    # SQLALCHEMY_DATABASE_URI = "mysql+pymysql://{}:{}@{}".format(MYSQL_USER, MYSQL_PW, MYSQL_URI)
    # SQLALCHEMY_DATABASE_URI = "mysql+pymysql://{}:{}@{}?charset=utf8&autocommit=true".format(MYSQL_USER, MYSQL_PW, MYSQL_URI)
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://{}:{}@{}?charset=utf8&autocommit=true')".format(MYSQL_USER, MYSQL_PW, MYSQL_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_SIZE = 1
    SQLALCHEMY_MAX_OVERFLOW = 0
    SQLALCHEMY_POOL_RECYCLE = 100


# redis基础配置
DATABASE_CONFIG = {
    'k8s-staging': {
        'host': 'k8s-staging.redis.zhangbei.rds.aliyuncs.com',
        'port': '6379',
        'db': 7,
        'password': 'SjJ8DEMtYrYYLIel',
        'max_connections': 10,
        'socket_connect_timeout': 0.5,
    },
    'k8s-prod': {
            'host': 'r-8vbabdc801a6a014.redis.zhangbei.rds.aliyuncs.com',
            'port': '6379',
            'db': 7,
            'password': '9G3F5pY9Il',
            'max_connections': 10,
            'socket_connect_timeout': 0.5,
        },
    'k8s-dev': {
            'host': 'r-8vb2570edobch2qstu.redis.zhangbei.rds.aliyuncs.com',
            'port': '6379',
            'db': 7,
            'password': 'yjse0R9wG81q',
            'max_connections': 10,
            'socket_connect_timeout': 0.5,
        },
    'defaults': {
        'host': '192.168.7.117',
        'port': '6379',
        'db': 1,
        'password': 'password',
        'max_connections': 10,
        'socket_connect_timeout': 0.5,
    },
    'local': {
            'host': '127.0.0.1',
            'port': '6379',
            'db': 1,
            'password': 'zichan360',
            'max_connections': 10,
            'socket_connect_timeout': 0.5,
        }
}




# redis用于连接连接池
REDIS_DB = {
    'host': env_dict.get("REDIS_HOST", DATABASE_CONFIG[SYSTEM_ENV]['host']),
    'port': env_dict.get("REDIS_PORT", DATABASE_CONFIG[SYSTEM_ENV]['port']),
    # 'db': env_dict.get("REDIS_DB", DATABASE_CONFIG[SYSTEM_ENV]['db']),
    # 默认 db=1
    'db': '1',
    'password': env_dict.get("REDIS_PASS", DATABASE_CONFIG[SYSTEM_ENV]['password']),
    'max_connections': env_dict.get("REDIS_MAX_CONNECTIONS",
                                    DATABASE_CONFIG[SYSTEM_ENV]['max_connections']),
    'socket_connect_timeout': env_dict.get("REDIS_SOCKET_CONNECT_TIMEOUT",
                                           DATABASE_CONFIG[SYSTEM_ENV]['socket_connect_timeout']),
}


# EXPIRE_TIME 单位是秒， redis失效时间
EXPIRE_TIME = 60*60*24*10

# log文件配置
log_dict = {'warning': logging.WARN, 'info': logging.INFO, 'error': logging.ERROR, 'debug': logging.DEBUG}
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "default": {'format': '%(asctime)s - %(filename)s - %(levelname)s - %(message)s'}
    },
    "handlers": {
        "info_file_handle": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "default",
            "filename": "log/info.log",
            "maxBytes": 10485760,
            # "maxBytes": 1024,
            "backupCount": 50,
            "encoding": "utf8"
        },
        "warning_file_handle": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "WARN",
            "formatter": "default",
            "filename": "log/warning.log",
            "maxBytes": 10485760,
            "backupCount": 50,
            "encoding": "utf8"
        },
        "error_file_handle": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "default",
            "filename": "log/error.log",
            "maxBytes": 10485760,
            "backupCount": 20,
            "encoding": "utf8"
        }
    },
    "root": {
        "level": log_dict[loglevel],
        "handlers": ["info_file_handle", "warning_file_handle", "error_file_handle"]
    }

}
logging.config.dictConfig(LOGGING_CONFIG)
