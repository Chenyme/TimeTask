import logging
from apscheduler.triggers.interval import IntervalTrigger
from logging.handlers import RotatingFileHandler
import importlib.util
import os
import subprocess
from datetime import datetime, timedelta, timezone, tzinfo
from contextlib import redirect_stdout, redirect_stderr
import io

# 定义东八区时区
class UTC8(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=8)

    def tzname(self, dt):
        return "UTC+8"

    def dst(self, dt):
        return timedelta(0)


utc8 = UTC8()

# 确保 logs 文件夹存在
remaining_times = {}
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)


# 创建日志记录器的函数，供每个操作使用
def get_task_logger(job_id):
    task_logger = logging.getLogger(f'task_logger_{job_id}')
    task_logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(message)s')
    log_file_path = os.path.join(log_dir, f'{job_id}.log')
    file_handler = RotatingFileHandler(log_file_path, maxBytes=20000, backupCount=5)
    file_handler.setFormatter(formatter)

    if not task_logger.hasHandlers():
        task_logger.addHandler(file_handler)

    return task_logger


def run_task(script_name, job_id, remark=""):
    script_path = os.path.join('tasks', script_name)
    task_logger = get_task_logger(job_id)
    task_logger.info(f"------TimeTask------\n")
    task_logger.info(f"开始执行任务: {script_name}")

    if not os.path.exists(script_path):
        error_msg = f"文件 {script_path} 未找到"
        task_logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    extension = script_name.rsplit('.', 1)[1].lower()

    try:
        if extension == 'py':
            # 动态加载并执行 Python 脚本，并捕获输出
            spec = importlib.util.spec_from_file_location(script_name, script_path)
            if spec is None:
                error_msg = f"无法加载文件 {script_path} 中的模块"
                task_logger.error(error_msg)
                raise ImportError(error_msg)

            module = importlib.util.module_from_spec(spec)

            # 重定向 stdout 和 stderr
            f_stdout = io.StringIO()
            f_stderr = io.StringIO()

            with redirect_stdout(f_stdout), redirect_stderr(f_stderr):
                spec.loader.exec_module(module)

            task_logger.info(f"*运行日志*\n{f_stdout.getvalue()}")
            if f_stderr.getvalue():
                task_logger.error(f"*错误日志*\n{f_stderr.getvalue()}")

            task_logger.info(f"任务 {script_name} 执行成功")

        elif extension in {'sh', 'bat', 'js'}:
            # 使用 subprocess 执行 shell 脚本, 批处理文件, 或 JavaScript 脚本
            if extension == 'sh':
                command = ["bash", script_path]
            elif extension == 'bat':
                command = [script_path]
            elif extension == 'js':
                command = ['node', script_path]

            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=(extension == 'bat'))

            # 将标准输出和标准错误记录到日志中
            if result.stdout:
                task_logger.info(f"标准输出:\n{result.stdout}")
            if result.stderr:
                task_logger.error(f"标准错误:\n{result.stderr}")

            if result.returncode == 0:
                task_logger.info(f"任务 {script_name} 执行成功")
            else:
                task_logger.error(f"运行文件 {script_path} 时发生错误，返回码: {result.returncode}")
                raise RuntimeError(result.stderr)

        else:
            error_msg = f"不支持的文件类型: {extension}"
            task_logger.error(error_msg)
            raise ValueError(error_msg)

    except Exception as e:
        error_msg = f"运行文件 {script_path} 时发生错误: {e}"
        task_logger.error(error_msg)
        raise RuntimeError(error_msg)


# 添加任务，关联自定义的任务ID和Python脚本
def add_task(scheduler, job_id, script_name, interval_seconds, remark=""):
    if scheduler.get_job(job_id):
        raise ValueError(f"任务ID {job_id} 已经存在")

    task_logger = get_task_logger(job_id)
    scheduler.add_job(
        id=job_id,
        func=run_task,
        trigger='interval',
        seconds=interval_seconds,
        kwargs={"script_name": script_name, "job_id": job_id, "remark": remark}
    )
    task_logger.info(f"任务添加成功: {job_id} ({script_name}), 执行间隔 {interval_seconds} 秒")


# 删除任务和对应的日志文件
def remove_task(scheduler, job_id):
    task_logger = get_task_logger(job_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        task_logger.info(f"任务删除成功: {job_id}")
        if job_id in remaining_times:
            del remaining_times[job_id]
            task_logger.info(f"删除任务 {job_id} 的剩余时间信息")
    else:
        task_logger.error(f"未找到ID为 {job_id} 的任务")
        raise ValueError(f"未找到ID为 {job_id} 的任务")

    # 移除并关闭所有与该任务相关的处理器
    handlers = task_logger.handlers[:]
    for handler in handlers:
        handler.close()
        task_logger.removeHandler(handler)

    # 删除对应的日志文件
    log_file_path = os.path.join(log_dir, f'{job_id}.log')
    if os.path.exists(log_file_path):
        try:
            os.remove(log_file_path)
            task_logger.info(f"日志文件删除成功: {log_file_path}")
        except Exception as e:
            task_logger.error(f"删除日志文件时发生错误: {e}")


# 更新任务的执行间隔
def update_task_interval(scheduler, job_id, interval_seconds):
    job = scheduler.get_job(job_id)
    task_logger = get_task_logger(job_id)
    if job:
        new_trigger = IntervalTrigger(seconds=interval_seconds)
        job.modify(trigger=new_trigger)
        task_logger.info(f"任务 {job_id} 的间隔更新为 {interval_seconds} 秒")
    else:
        error_msg = f"未找到ID为 {job_id} 的任务"
        task_logger.error(error_msg)
        raise ValueError(error_msg)




def pause_task(scheduler, job_id):
    job = scheduler.get_job(job_id)
    task_logger = get_task_logger(job_id)
    if job:
        # 统一使用东八区时间进行计算
        remaining_time = (job.next_run_time.astimezone(utc8) - datetime.now(utc8)).total_seconds()
        remaining_times[job_id] = remaining_time
        task_logger.info(f"任务暂停成功: {job_id}，剩余时间: {remaining_time} 秒，原时间 {job.next_run_time.astimezone(utc8)}")
        scheduler.pause_job(job_id)
    else:
        task_logger.error(f"未找到ID为 {job_id} 的任务")
        raise ValueError(f"未找到ID为 {job_id} 的任务")


def resume_task(scheduler, job_id):
    job = scheduler.get_job(job_id)
    task_logger = get_task_logger(job_id)
    if job:
        # 获取任务的原始参数
        interval_seconds = job.trigger.interval.total_seconds()  # 假设使用的是IntervalTrigger
        script_name = job.kwargs.get('script_name')
        remark = job.kwargs.get('remark', "")

        remaining_time = remaining_times.get(job_id)
        if remaining_time is not None:
            # 计算新的下次执行时间
            next_run_time = datetime.now(timezone.utc) + timedelta(seconds=remaining_time)

            # 移除旧任务
            scheduler.remove_job(job_id)

            # 重新添加任务
            scheduler.add_job(
                id=job_id,
                func=run_task,
                trigger=IntervalTrigger(seconds=interval_seconds, start_date=next_run_time),
                kwargs={"script_name": script_name, "job_id": job_id, "remark": remark}
            )
            del remaining_times[job_id]
            task_logger.info(f"任务恢复成功: {job_id}，将在 {remaining_time} 秒后运行，时间为 {next_run_time}")
        else:
            task_logger.warning(f"任务 {job_id} 没有剩余时间记录，按原计划运行")
    else:
        task_logger.error(f"未找到ID为 {job_id} 的任务")
        raise ValueError(f"未找到ID为 {job_id} 的任务")


