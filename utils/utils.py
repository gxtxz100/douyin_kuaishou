# -*- coding: utf-8 -*-
# @Samp: pip install pycryptodome -i https://pypi.tuna.tsinghua.edu.cn/simple
# @Time: 2024/12/28 0:37
# @Author: jef.ld
# @Project: douyin_spider
# @File: common
import configparser
import chardet
import os
import re
import traceback


class Utils:
    # 获取当前路径
    @classmethod
    def get_current_path(cls, filepath: tuple[str, ...], filename=None):
        """
        获取上级目录，然后通过参数进行拼接获取目标路径
        """
        if not isinstance(filepath, tuple):
            print("filepath error 请传元组对象")
            raise TypeError

        curr = os.path.dirname(__file__)
        curr = os.path.abspath(os.path.join(curr, ".."))
        if filename is None:
            curr = os.path.join(curr, *filepath)
        else:
            curr = os.path.join(curr, *filepath, filename)
        return curr

    @classmethod
    def read_config(cls, filepath: tuple[str, ...], filename, encoding=None):
        """
        读取配置文件
        :return:
        """
        if encoding is None:
            ecod = cls.detect_file_encoding(filepath, filename)
            if ecod is None:
                print("获取文件编码失败，文件不存在")
                return ecod
        else:
            ecod = encoding
            print("指定文件编码格式：{}".format(ecod))
        file = cls.get_current_path(filepath, filename)
        conf = configparser.RawConfigParser()

        try:
            conf.read(file, encoding=ecod)
            return conf
        except UnicodeDecodeError:
            ecod = cls.detect_file_encoding(filepath, filename, is_full=True)
            conf.read(file, encoding=ecod)
            return conf
        except Exception as e:
            print(e)
            return None

    @classmethod
    def read_file(cls, filepath: tuple[str, ...], filename, encoding=None):
        if encoding is None:
            ecod = cls.detect_file_encoding(filepath, filename)
            if ecod is None:
                print("获取文件编码失败，文件不存在")
                return ecod
        else:
            ecod = encoding
            print("指定文件编码格式：{}".format(ecod))
        file = cls.get_current_path(filepath, filename)
        try:
            with open(file, mode="r", encoding=ecod) as f:
                data = f.read()
            return data
        except UnicodeDecodeError:
            ecod = cls.detect_file_encoding(filepath, filename, is_full=True)
            with open(file, mode="r", encoding=ecod) as f:
                data = f.read()
            return data

    @classmethod
    def folders_create(cls, filepath: tuple[str, ...]):
        """
        用于创建目录
        :return:
        """
        path = cls.get_current_path(filepath=filepath)
        if not os.path.exists(path):
            os.makedirs(path)
            # log.info("创建目录：{}".format(path))
            print("创建目录：{}".format(path))

    # 获取文件的编码
    @classmethod
    def detect_file_encoding(cls, filepath: tuple[str, ...], filename, is_full=False):
        """
        主要是用来获取不同文件的编码，方便读取
        :param is_full:
        :param filename:
        :param filepath:
        :return:
        """
        stack = traceback.extract_stack()
        caller = stack[-2]  # 上一层栈帧

        file = cls.get_current_path(filepath, filename)
        if not os.path.isfile(file):
            # log.error("No such file or directory: {}".format(filename))
            print("No such file or directory: {}".format(file))
            return None

        with open(file, mode="rb") as f:
            # raw_data = f.read() # 这种效率有点慢，对于大文件时
            if is_full:
                print("读取全部文件获取编码:{}".format(caller))
                raw_data = f.read()
            else:
                print("按部分文件获取编码:{}".format(caller))
                raw_data = f.read()[0:10240]  # 只截取一部分
            result = chardet.detect(raw_data)
            return result["encoding"]

    @staticmethod
    def teshu(sstr):
        new_str = re.sub(r'[?|\\/:：!&#*\[\]\n\s\t]', '_', sstr)
        if len(new_str) > 31:
            new_str = new_str[0:31]
        return new_str

    def get_file_no3(self, filepath: tuple[str, ...], filename, fno: int):
        """
        按文件名来统一编号：
        file1_00001、file1_00002
        file2_00001、file2_00002
        """
        if not os.path.exists(self.get_current_path(filepath)):
            print("目录不存在~")
            return None

        file_ext = os.path.splitext(filename)
        if file_ext[1] in ("", "."):
            print("Warning: filename-->", filename)  # 文件名可能不符合规范，需要注意一下
        no1 = re.search("_([0-9]{5})$", file_ext[0])  # 获取文件原先的编号
        if no1 is None:
            file_no_ext = file_ext[0]
        else:
            # 如果文件存在符合规范的编号，且不在文件中存在，直接返回
            file = self.get_current_path(filepath, filename)
            if not os.path.isfile(file):
                return {"file": filename, "fno": fno}

            file_no_ext = file_ext[0][:-6]

        files = (f.name for f in os.scandir(self.get_current_path(filepath)) if f.is_file())
        files_count = sum(1 for f in os.scandir(self.get_current_path(filepath)) if f.is_file())

        for fno in range(1, files_count + 2):
            file = file_no_ext + "_%05d" % fno + file_ext[1]
            if file not in files:
                return {"file": file, "fno": fno}
        else:
            print("匹配失败~")
            return None

    @staticmethod
    def truncate_string(s: str, max_length: int):
        if max_length <= 4:
            return "%s..." % (s[:3])
        elif len(s) > max_length:
            half_length = max_length // 3
            # 不包括省略号，需要包括的话再减3
            end_length = max_length - half_length

            if end_length == 0:
                ed_str = ""
            elif end_length < 0:
                ed_str = s[end_length:]
            else:
                ed_str = s[-end_length:]
            return "%s...%s" % (s[:half_length], ed_str)
        else:
            return s
