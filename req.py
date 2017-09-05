import requests
from urllib import request
import os
import json
import threadpool
from retry import retry
import config
import log


# get db file,return is it newer
@retry(stop_max_attempt_number=config.retry_db,
       wait_exponential_multiplier=config.slience_db_multiplier * 1000,
       wait_exponential_max=config.slience_db_multiplier_max * 1000)
def get_db_file(db_url, db_file):
    # return True

    ctime_old = None
    if os.path.exists(db_file):
        ctime_old = os.stat(db_file).st_ctime
    request.urlretrieve(db_url, db_file)
    ctime = os.stat(db_file).st_ctime

    if not ctime_old or ctime_old < ctime:
        return True
    else:
        return False


# batch post data to webservice
def post_data(url, data_list):
    try:
        # for d in data_list:
        #     print(d)

        if config.enable_thread:  # multi thread
            args = []
            for d in data_list:
                args.append(([url, d], None))
            pool = threadpool.ThreadPool(config.thread_pool_size)
            reqs = threadpool.makeRequests(post_except, args, finished)
            [pool.putRequest(req) for req in reqs]
            pool.wait()
            args.clear()
        else:  # single thread
            #post_except(url, data_list)
            for d in data_list:
                res = post_except(url, d, True)
    except Exception:
        raise


# post callback
def finished(*args, **kwargs):
    global COUNT
    print("finished  ",args)
    if args[1]:
        print(args[1])
        if args[1].status_code == 201:
            COUNT += 1
        else:
            log.log_error("post data failed\ncode:%d\nresponse:%s\npost_data data:%s"
                          % (args[1].status_code, args[1].text, args[0]))


# no exception handle, for implement retrying
@retry(stop_max_attempt_number=config.retry_http,
       wait_exponential_multiplier=config.slience_http_multiplier*1000,
       wait_exponential_max=config.slience_http_multiplier_max*1000)
def post_retry(url, data, is_json=True):
    print("try…… ", end="")
    try:
        if is_json:
            return requests.post(url, json=json.dumps(data), timeout=config.timeout_http)
        else:
            return requests.post(url, data=data, timeout=config.timeout_http)
    except Exception as e:
        print(str(e))
        raise

# have exception handle, for implement multi thread
def post_except(url, data, is_json=True):
    global SUCCESS_COUNT
    print("post_except:", url)
    try:
        res = post_retry(url, data, is_json)
        if res.status_code == 201:
            SUCCESS_COUNT += 1
        else:
            log.log_error("post data failed\ncode:%d\nresponse:%s\npost_data data:%s"
                          % (res.status_code, res.text, data))
        return res
    except Exception as e:
        log.log_error("server error:" + str(e) + "\ndata:" + str(data))

