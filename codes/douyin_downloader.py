# -*- coding: utf-8 -*-
import time
import sys
import os

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import subprocess
import asyncio
import aiohttp
import json
import aiofiles
from yarl import URL
from aiohttp import ClientError, ConnectionTimeoutError, ClientConnectorError
from asyncio.exceptions import TimeoutError
from utils.utils import Utils

class DouyinDownloader(Utils):
    def __init__(self):
        self.lock = asyncio.Lock()
        self.config = self.read_config(filepath=("config",), filename="config.ini")
        self.timeout = 60  # 增加超时时间到60秒
        self.rep_count = self.config.getint("options", "rep_count")
        self.download_dir = self.config.get("download_info", "filepath")

    @staticmethod
    async def get_audio_info(session, text):
        url = "https://su.tuanyougou.com/query"
        params = {
            "url": text,
            "token": "",
            "id": "",
            "user_id": "1"
        }
        async with session.request(method="GET", url=URL(url, encoded=True), params=params) as resp:
            if resp.status != 200:
                return None
            return json.loads(await resp.text())

    def data_parse(self, data):
        if not data or "data" not in data:
            return None

        title = self.teshu(data["data"]["title"])
        # 优先选取最小码率音频
        audio_keys = [
            "audio_32k_url", "audio_64k_url", "audio_128k_url",
            "mp3play_url", "m4a_url", "audio_url", "music", "music_url"
        ]
        downurl = None
        for key in audio_keys:
            if key in data["data"] and data["data"][key]:
                downurl = data["data"][key]
                break
        # 如果都没有，使用视频链接
        if not downurl and "downurl" in data["data"]:
            downurl = data["data"]["downurl"]

        if not downurl:
            print("未找到下载链接")
            return None

        self.folders_create(filepath=(self.download_dir,))
        filename = f"{title}.mp3"
        file = self.get_current_path(filepath=(self.download_dir,), filename=filename)

        return {
            "title": filename,
            "truncate_name": self.truncate_string(filename, 30),
            "filepath": file,
            "url": downurl,
            "is_video": not any(downurl.endswith(ext) for ext in [".mp3", ".m4a"])
        }

    async def download_with_ffmpeg(self, session, url, filepath, truncate_name):
        """使用ffmpeg下载并转码视频"""
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", url,  # 直接使用URL作为输入
            "-vn",  # 不处理视频
            "-acodec", "libmp3lame",  # 使用mp3编码器
            "-ar", "44100",  # 采样率
            "-ab", "32k",  # 比特率
            "-f", "mp3",  # 输出格式
            filepath
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
                return filepath
            else:
                print(f"[{truncate_name}] ffmpeg错误: {stderr.decode()}")
                return None
        except Exception as e:
            print(f"[{truncate_name}] ffmpeg执行错误: {e}")
            return None

    async def download(self, semaphore, session, **info):
        await asyncio.sleep(0.2)
        async with self.lock:
            print("正在下载:", info["truncate_name"])

        async with semaphore:
            for rep in range(1, self.rep_count + 1):
                try:
                    url = info["url"]
                    if not info.get("is_video"):
                        # 直接下载音频
                        async with session.request(method="GET", url=URL(url, encoded=True), timeout=self.timeout) as resp:
                            if resp.status == 200:
                                async with aiofiles.open(info["filepath"], mode="wb") as f:
                                    async for b in resp.content.iter_chunked(1024 * 1024):
                                        if b:
                                            await f.write(b)
                                if os.path.isfile(info["filepath"]) and os.path.getsize(info["filepath"]) > 0:
                                    return info["filepath"]
                                else:
                                    return f"[{info['truncate_name']}] 下载失败~"
                            else:
                                print(f"[{info['truncate_name']}] 请求失败: {resp.status}")
                                print(f"重试中...{rep}/{self.rep_count}")
                    else:
                        # 使用ffmpeg直接下载并转码
                        print(f"[{info['truncate_name']}] 使用ffmpeg下载并转码为32k mp3")
                        result = await self.download_with_ffmpeg(
                            session, url, info["filepath"], info["truncate_name"]
                        )
                        if result:
                            return result
                        print(f"重试中...{rep}/{self.rep_count}")
                        
                except (ClientError, ConnectionTimeoutError, ClientConnectorError) as e:
                    print(f"[{info['truncate_name']}] 下载文件时出错: {e}")
                    print(f"等待 2 秒后重试...{rep}/{self.rep_count}")
                    await asyncio.sleep(2)
                except TimeoutError as e:
                    print(f"[{info['truncate_name']}] 下载文件时超时: {repr(e)}")
                    print(f"等待 2 秒后重试...{rep}/{self.rep_count}")
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"[{info['truncate_name']}] 其它异常: {e}")
                    return f"[{info['truncate_name']}] 下载异常~"
            return f"[{info['truncate_name']}] 下载失败~"

    async def process_url(self, session, url):
        response = await self.get_audio_info(session, url)
        if not response:
            print(f"无法获取链接信息: {url}")
            return None
            
        data = self.data_parse(response)
        if not data:
            print(f"解析数据失败: {url}")
            return None
            
        return data

    async def client(self, urls):
        semaphore = asyncio.Semaphore(1)  # 限制并发数为1
        async with aiohttp.ClientSession() as session:
            tasks = []
            for url in urls:
                url = url.strip()
                if url:
                    task = asyncio.create_task(self.process_url(session, url))
                    tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            download_tasks = []
            
            for result in results:
                if result:
                    download_tasks.append(asyncio.create_task(self.download(semaphore, session, **result)))
            
            totals = len(download_tasks)
            suc_num = 1
            print(f"[*] 待下载任务:[{totals}]")

            for task in download_tasks:
                ret = await task
                print(f"[*] 已完成: [{suc_num}/{totals}] 下载路径:{ret}")
                suc_num += 1

    def read_urls_from_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"读取文件失败: {e}")
            return []

    def main(self):
        file_path = input("请输入包含抖音链接的txt文件路径: ")
        if not os.path.exists(file_path):
            print("文件不存在！")
            return
            
        urls = self.read_urls_from_file(file_path)
        if not urls:
            print("文件中没有找到有效的链接！")
            return
            
        print(f"共找到 {len(urls)} 个链接")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.client(urls))

if __name__ == '__main__':
    downloader = DouyinDownloader()
    downloader.main() 