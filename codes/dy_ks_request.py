# -*- coding: utf-8 -*-
# @Samp: pip install pycryptodome -i https://pypi.tuna.tsinghua.edu.cn/simple
# @Time: 2025/4/16 17:52
# @Author: jef.ld
# @Project: qq_space
# @File: demo
import time

import aiohttp
import asyncio
import json
import os
import aiofiles
from utils.utils import Utils
from yarl import URL
from aiohttp import ClientError, ConnectionTimeoutError, ClientConnectorError
from asyncio.exceptions import TimeoutError


class Down(Utils):
    def __init__(self):
        self.lock = asyncio.Lock()
        self.config = self.read_config(filepath=("config",), filename="config.ini")
        self.timeout = self.config.getint("options", "timeout")
        self.rep_count = self.config.getint("options", "rep_count")

    @staticmethod
    async def get_pic_vid(session, text):
        url = "https://su.tuanyougou.com/query"
        params = {
            "url": text,
            "token": "",
            "id": "",
            "user_id": "1"
        }
        async with session.request(method="GET", url=URL(url, encoded=True), params=params) as resp:
            if resp.status != 200:
                return
            return json.loads(await resp.text())

    def data_parse(self, data):
        title = self.teshu(data["data"]["title"])
        typ = data["data"]["type"]
        downurl = data["data"]["downurl"]
        pics = data["data"]["pics"]

        all_opus = []  # 所有作品
        date = time.strftime("%Y年%m月")
        down_filepath = self.config.get("download_info", "filepath")
        if typ == 1:
            filepath = self.get_current_path(filepath=(down_filepath, date, "videos", title))
            self.folders_create(filepath=(filepath,))

            num = 1
            file_no = self.get_file_no3(filepath=(filepath,), filename=title + "_%05d.mp4" % (num,), fno=num)
            filename = file_no["file"]

            file = self.get_current_path(filepath=(filepath,), filename=filename)
            all_opus.append({"title": filename, "truncate_name": self.truncate_string(filename, 30), "filepath": file,
                             "url": downurl})
        elif typ == 2:
            filepath = self.get_current_path(filepath=(down_filepath, date, "images", title))
            self.folders_create(filepath=(filepath,))

            filenames = set()
            num = 1
            for v in pics:
                while True:
                    file_no = self.get_file_no3(filepath=(filepath,), filename=title + "_%05d.png" % (num,), fno=num)
                    filename = file_no["file"]
                    if filename not in filenames:
                        filenames.add(filename)
                        num = file_no["fno"] + 1
                        break
                    else:
                        num += 1
                file = self.get_current_path(filepath=(filepath,), filename=filename)
                all_opus.append(
                    {"title": filename, "truncate_name": self.truncate_string(filename, 30), "filepath": file,
                     "url": v})
        else:
            print("作品类型有误")
            return None
        return all_opus

    async def download(self, semaphore, session, **info):
        await asyncio.sleep(0.2)
        async with self.lock:
            print("正在下载:", info["truncate_name"])

        async with semaphore:
            for rep in range(1, self.rep_count + 1):
                try:
                    async with session.request(method="GET", url=URL(info["url"], encoded=True),
                                               timeout=self.timeout) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(info["filepath"], mode="wb") as f:
                                async for b in resp.content.iter_chunked(1024 * 1024):
                                    if b:
                                        await f.write(b)
                            if os.path.isfile(info["filepath"]) and os.path.getsize(info["filepath"]) > 0:
                                return info["filepath"]
                            else:
                                return "[{}] 下载失败~".format(info["truncate_name"])
                        else:
                            print("[{}] 请求失败:".format(info["truncate_name"], resp.status))
                            print("重试中...{}/{}".format(rep, self.rep_count))
                except (ClientError, ConnectionTimeoutError, ClientConnectorError) as e:
                    print("[{}] 下载文件时出错\n:{}".format(info["truncate_name"], e))
                    print("等待 2 秒后重试...{}/{}".format(rep, self.rep_count))
                    await asyncio.sleep(2)  # 延迟后重试
                except TimeoutError as e:
                    print("[{}] 下载文件时超时\n:{}".format(info["truncate_name"], repr(e)))
                    print("等待 2 秒后重试...{}/{}".format(rep, self.rep_count))
                    await asyncio.sleep(2)  # 延迟后重试
                except Exception as e:
                    print("[{}] 其它异常\n:{}".format(info["truncate_name"], e))
                    return "[{}] 下载异常~".format(info["truncate_name"])
            else:
                return "[{}] 下载失败~".format(info["truncate_name"])

    async def client(self, text: str):
        semaphore = asyncio.Semaphore(10)
        async with aiohttp.ClientSession() as session:
            response = await self.get_pic_vid(session, text)

            data_list = self.data_parse(response)
            totals = len(data_list)
            suc_num = 1
            print("[*] 待下载任务:[{}]".format(totals))

            tasks = [asyncio.create_task(self.download(semaphore, session, **ts)) for ts in data_list]
            for task in asyncio.as_completed(tasks):
                ret = await task
                print("[*] 已完成: [{}/{}] 下载路径:{}".format(suc_num, totals, ret))
                suc_num += 1

    def main(self):
        text = input("请输入链接:")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.client(text))

    def debug(self):
        pass


if __name__ == '__main__':
    down = Down()
    down.main()
