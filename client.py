import socket
from config.config import *
import time
import random
import subprocess
import threading
from actuator_impl import ActuatorImpl
import json
import logging


# 生成高斯分布的随机数，对应于cpu限制
def generate_truncated_normal(mean, std_dev, lower, upper):
    sample = random.gauss(mean, std_dev)
    if lower <= sample <= upper:
        return sample
    else:
        return generate_truncated_normal(mean, std_dev, lower, upper)


# 获取容器id
def get_container_id():
    try:
        with open('/etc/hostname', 'r') as f:
            return f.read()
    except FileNotFoundError:
        logging.info("filenotfound")  # 如果文件不存在，返回None
    except Exception as e:
        logging.info("An error occurred:", e)
    return None


class Client:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 128000000)
    addr = (HOST, PORT)
    compute_flag = True
    assigned_task = None
    client_id = get_container_id() if get_container_id() else '1'
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

    @classmethod
    def client(cls):
        # 接受任务
        cls.receive_task()
        # 计算任务，回传结果
        monitor_thread = threading.Thread(target=cls.monitor)
        monitor_thread.start()
        compute_thread = threading.Thread(target=cls.compute_task)
        compute_thread.start()

    @classmethod
    def monitor(cls):
        while True:
            try:
                delay_msg = 'delay:' + cls.client_id
                cls.sock.sendto(delay_msg.encode('utf-8'), cls.addr)
                # logging.info("delay sent success")
            except (OSError, cls.sock.error) as e:
                logging.info("delay sent error", e)
                return e.errno
            time.sleep(1)

    @classmethod
    def receive_task(cls):
        try:
            hello_msg = 'hello from:' + cls.client_id
            cls.sock.sendto(hello_msg.encode('utf-8'), cls.addr)
            logging.info("hello sent success")
        except (OSError, cls.sock.error) as e:
            logging.info("hello sent error", e)
            return e.errno

        data, addr = cls.sock.recvfrom(CHUNK_SIZE)
        json_data = data.decode('utf-8')
        cls.assigned_task = json.loads(json_data)
        logging.info(cls.assigned_task)

        file_data = b''
        while True:
            data, addr = cls.sock.recvfrom(CHUNK_SIZE)
            if data.decode('utf-8').startswith('EOF'):
                break
            file_data += data
        # 将接收到的数据保存成文件
        with open('compute_task_r.py', 'wb') as file:
            file.write(file_data)
        logging.info("File received successfully.")

    @classmethod
    def compute_task(cls):
        while len(cls.assigned_task):
            start_time = time.perf_counter()
            result = ActuatorImpl.run_actuator('compute_task_r')
            end_time = time.perf_counter()
            time_taken = round(end_time - start_time, 2)
            result_msg = 'result :' + str(result) + ':' + cls.client_id + ':' + str(
                cls.assigned_task[0]) + ':' + str(
                time_taken)
            logging.info(result_msg)
            try:
                cls.sock.sendto(result_msg.encode('utf-8'), cls.addr)
                logging.info("result sent success")
            except (OSError, cls.sock.error) as e:
                logging.info("result sent error:", e)
                return e.errno

            cls.assigned_task.pop(0)

        cls.compute_flag = False
        logging.info('all task completed')


if __name__ == '__main__':
    Client.client()
    # result='result:123213123:sxdah1:6:2.33'
    # print(result.split(':'))
    # logging.info(generate_truncated_normal(3, 1, 2, 4))
    # data='result:59.67:a12a4fe19a43'
    # if data.startswith('result'):
    #     print(data)
