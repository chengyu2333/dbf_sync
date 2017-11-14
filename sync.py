# -*- coding: utf-8 -*
import time
import shutil
import os
from retry import retry
from simpledbf import Dbf5
from pandas import concat
import config
from log import Log
from dbfread import DBF
from map_dict import map_dict
from req import Req


class Sync:
    def __init__(self):
        self.req = Req(retry_http=config.retry_http,
                  silence_http_multiplier=config.silence_http_multiplier,
                  silence_http_multiplier_max=config.silence_http_multiplier_max,
                  timeout_http=config.timeout_http)
        self.log = Log(print_log=config.print_log)
        self.db_now = ""
        self.db_prev = ""
        self.table = None
        self.table_prev = None
        self.new_data = []

    @retry(stop_max_attempt_number=1,
           wait_exponential_multiplier=2000,
           wait_exponential_max=10000)
    def get(self, db_now=None, db_prev=None, get_all=""):
        """
        获取数据
        :return: DataFrame: (table，table_prev)
        """
        start_time = time.time()
        if db_now or db_prev:
            self.db_now, self.db_prev = db_now, db_prev
        else:
            self.db_now, self.db_prev = self.req.get_db_file()

        # 读文件表
        try:
            # if get_all:
            #     print(get_all)
            #     if os.path.exists(get_all):
            #         self.table = Dbf5(get_all, codec="gbk").to_dataframe()
            #         return self.table
            #     return False

            # db_now不存在
            if not self.db_now or not os.path.exists(self.db_now):
                # if get_all:  # 取得全部数据
                #     if self.db_prev or not os.path.exists(self.db_prev):
                #         self.table = Dbf5(self.db_prev, codec="gbk").to_dataframe()
                #     else:
                #         print("file not exist")
                #         return False
                # else:
                #     return False
                return False
            else:
                self.table = Dbf5(self.db_now, codec="gbk").to_dataframe()
                if self.db_prev is not None:
                    if os.path.exists(self.db_prev):
                        self.table_prev = Dbf5(self.db_prev, codec="gbk").to_dataframe()

            self.log.log_success("Read data spend:{time}s | prev dbf []: {db_prev} | now dbf []:{db_now}".
                                 format(time="%.2f" % (time.time()-start_time),
                                        db_prev=str(self.db_prev),
                                        db_now=str(self.db_now)))
            return self.table, self.table_prev
        except Exception as e:
            self.log.log_error(str(e))
            raise

    @retry(stop_max_attempt_number=3,
           wait_exponential_multiplier=2000,
           wait_exponential_max=10000)
    def process(self, table=None, table_prev=None):
        """
        处理、映射表数据,table_prev为空时为全部
        :param table: 
        :param table_prev: 
        :return: new_data
        """
        start_time = time.time()
        # 原始数据
        table = table or self.table
        table_prev = table_prev or self.table_prev
        # 处理对比数据
        if table_prev is not None and not table_prev.empty:
            l = len(table_prev)
        else:
            l = 0
        dl = []
        df = concat([table_prev, table], ignore_index=True).drop_duplicates().ix[l:, :]

        # 如果update_at不是今天，那么就设置为今天 (for data template)
        up_data = df[df['HQZQDM']=="000000"]['HQZQJC'].values[0]
        up_time = df[df['HQZQDM']=="000000"]['HQCJBS'].values[0]
        if str(up_data) == time.strftime("%Y%m%d") or True:
            updated_at = str(up_data) + str(up_time)
            updated_at = time.strptime(updated_at, "%Y%m%d%H%M%S")
            updated_at = time.strftime("%Y-%m-%dT%H:%M:%S", updated_at)
        else:
            updated_at = time.strftime("%Y-%m-%dT09:10:00")

        for row in df.iterrows():
            d = row[1].to_dict()
            if d['HQZQDM'] == "899002":
                print(d)
                exit()
            d['updated_at'] = updated_at
            # 降低精度
            for r in d:
                if isinstance(d[r], float):
                    d[r] = "%.2f" % d[r]
            dl.append(d)

        # map dict
        new_data, total = map_dict(dl,
                                   config.map_rule['map'],
                                   config.map_rule['strict'],
                                   config.map_rule['lower'],
                                   swap=config.map_rule['swap'])
        # update db cache
        self.new_data = new_data
        self.log.log_success("Process spend: {time}s | update at: {up_at} | new record: {new}"
                             .format(up_at=updated_at,  new=total,
                                     time="%.2f" % (time.time() - start_time)))
        return new_data

    @retry(stop_max_attempt_number=3,
           wait_exponential_multiplier=2000,
           wait_exponential_max=10000)
    def upload(self, data=None):
        """
        上传数据
        :param data: dict data
        :return: True or False
        """

        start_time = time.time()
        data = data or self.new_data
        self.log.log_success("Start commit, total:" + str(len(data)))
        # start commit all data
        try:
            self.req.commit_data_list(post_url=config.api_post,
                                      data_list=data,
                                      post_json=config.post_json,
                                      enable_thread=config.enable_thread,
                                      thread_pool_size=config.thread_pool_size,
                                      post_success_code=config.post_success_code)
        except Exception as e:
            self.log.log_error(str(e))
            return False
        self.new_data = None
        self.log.log_success("Commit finished,spend time:" + "%.2f" % (time.time() - start_time))
        return True

    @staticmethod
    def reset():
        """重置缓存"""
        # 要删除的文件列表
        del_list = ["tmp/id_cache.txt", "tmp/old_time.tmp"]
        for d in del_list:
            if os.path.exists(d):
                os.remove(d)

    def cache_id_all(self):
        """缓存全部id"""
        table = DBF(config.prev_file, encoding="gbk", char_decode_errors="ignore")
        for record in table:
            try:
                print(record["HQZQDM"], "  ", self.req.cache_id(record["HQZQDM"]))
            except Exception as e:
                print(str(e))
