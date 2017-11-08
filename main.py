# -*- coding: utf-8 -*
import time
import config
from cache import Cache
from log import Log
from sync import Sync
from req import GetReq as req_get
from cron import Cron
from tools import in_time_range
import os

log = Log(config.print_log)
cache_last_run = Cache("tmp/last_run.tmp")
cron = Cron(config.time_range_sync)


# 周期执行函数
def cycle_exec(cycle_time=10):
    last_time_sync = time.time()
    log = Log(print_log=config.print_log)
    data_cache = []
    sync = Sync()
    while True:
        start_time_cycle = time.time()

        # 判断时间段
        if config.time_range_sync:
            if not in_time_range(config.time_range_sync):
                time.sleep(10)
                continue
        try:

            # 检查今天是否同步过，否则初始化系统
            if not cache_last_run.get_value(time.strftime("%Y%m%d")):
                print("reset")
                sync.reset()
                sync.get(get_all=True)
                data = sync.process()
                sync.upload(data)
                # sync.cache_id_all()  # 缓存所有Id
                cache_last_run.append(time.strftime("%Y%m%d"), "1")
                # sync.sync()
                continue

            # 检查API是否正常
            # error_count = process.check_random()
            # error_count = 0
            # if error_count > 4:
            #     log.log_error("API error ，reupload template" + " miss count" + str(error_count))
            #     sync.reset()
            #     time.sleep(60)
            #     continue

            # 获取待同步文件
            if not sync.get():
                print("sync finishd")
                time.sleep(10)
                continue

            # 直接获取待同步数据，不做缓存
            # data_cache += sync.process()

            # 缓存待同步数据，多批数据只保留最新的更新时间
            data = sync.process()

            if len(data) == 1:
                if len(data_cache) == 0:
                    data_cache.append(data[0])
                else:
                    data_cache[0] = data[0]
            elif len(data) > 1:
                for d in data:
                    if d['hqzqdm'] == "000000":
                        if len(data_cache) == 0:
                            data_cache.append(d)
                        else:
                            data_cache[0] = d
                        data.remove(d)

                data_cache += data

            # 开始提交数据 (数据为1时则没有变化)
            # 第一层验证：待同步数据大于n条时则提交
            # 第二层验证：每隔t秒提交一次
            n = 2  # 如果为2，表示只有时间变动，不需要提交
            t = 30
            if len(data_cache) >= n:
                print(" ", len(data_cache), end="")
                if len(data_cache) > 10:  # 超过10则立即同步
                    last_time_sync = time.time()  # 重置上次同步的时间
                    sync.upload(data_cache)
                    data_cache.clear()
                    continue
                if time.time() - last_time_sync > t:
                    last_time_sync = time.time()
                    sync.upload(data_cache)
                    data_cache.clear()
                    continue

        except Exception as e:
            log.log_error(str(e))
            raise

        # 保证最小周期时间
        end_time = time.time()
        sleep_time = cycle_time - (end_time - start_time_cycle)
        sleep_time = sleep_time if sleep_time >= 0 else 0
        print('waiting…… %ds' % sleep_time)
        time.sleep(sleep_time)
        start_time_cycle = time.time()


if __name__ == "__main__":
    print("===== synchronize start =====")
    cycle_exec(cycle_time=config.cycle_time)

