import os
import zipfile
from functools import wraps
from flask_admin import Admin
from datetime import datetime, timezone
from flask_apscheduler import APScheduler
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session


app = Flask(__name__)
app.secret_key = 'supersecretkey'


class Config:  # 配置任务调度器
    SCHEDULER_API_ENABLED = True
    UPLOAD_FOLDER = 'tasks'


app.config.from_object(Config())


if not os.path.exists(app.config['UPLOAD_FOLDER']):  # 确保上传文件夹存在
    os.makedirs(app.config['UPLOAD_FOLDER'])

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

admin = Admin(app, name='任务管理器')  # 配置 Flask-Admin

with open('.env') as f:
    for line in f:
        name, value = line.strip().split('=', 1)
        os.environ[name] = value

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'py', 'sh', 'js', 'bat'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_edit_file(filename):
    ALLOWED_EXTENSIONS = {'py', 'sh', 'js', 'bat'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def format_interval(seconds):
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}:{hours}:{minutes}:{seconds}"


# 登录保护装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# 登录页面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            flash('登录成功！', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('您已成功登出', 'success')
    return redirect(url_for('login'))


@app.context_processor
def utility_processor():
    return dict(format_interval=format_interval)


@app.route('/')
@login_required
def index():
    jobs = scheduler.get_jobs()
    files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if allowed_file(f)]
    python_files = [f for f in files if f.endswith('.py') or f.endswith('.sh') or f.endswith('.js') or f.endswith('.bat')]

    # 创建一个包含任务和剩余时间的列表
    job_info = []
    for job in jobs:
        if job.next_run_time:
            remaining_time = int((job.next_run_time - datetime.now(timezone.utc)).total_seconds())
        else:
            remaining_time = None
        job_info.append({
            'job': job,
            'remaining_time': remaining_time
        })

    return render_template('index.html', job_info=job_info, python_files=python_files)


@app.route('/scripts')
@login_required
def script_management():
    files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if allowed_file(f)]
    return render_template('script_management.html', files=files)


# 文件上传
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash('文件上传成功！', 'success')
    else:
        flash('无效的文件类型。', 'error')
    return redirect(url_for('script_management'))


# 文件列表
@app.route('/files')
@login_required
def list_files():
    files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if allowed_file(f)]
    return render_template('files.html', files=files)


# 批量删除
@app.route('/batch_delete', methods=['POST'])
@login_required
def batch_delete_files():
    selected_files = request.form.getlist('selected_files')
    if not selected_files:
        flash('请选择至少一个文件进行删除。', 'error')
        return redirect(url_for('script_management'))

    for filename in selected_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            flash(f'文件 {filename} 已删除！', 'success')
        else:
            flash(f'文件 {filename} 不存在。', 'error')

    return redirect(url_for('script_management'))


# 批量下载
@app.route('/batch_download', methods=['POST'])
@login_required
def batch_download_files():
    selected_files = request.form.getlist('selected_files')
    if not selected_files:
        flash('请选择至少一个文件进行下载。', 'error')
        return redirect(url_for('script_management'))

    # 确保 cache 目录存在
    cache_dir = os.path.join('cache')
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    zip_filename = "files.zip"
    zip_filepath = os.path.join(cache_dir, zip_filename)

    with zipfile.ZipFile(zip_filepath, 'w') as zipf:
        for filename in selected_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                zipf.write(file_path, arcname=filename)
            else:
                flash(f'文件 {filename} 不存在。', 'error')
                return redirect(url_for('script_management'))

    # 确保文件在正确的位置，并在缓存目录下
    if not os.path.exists(zip_filepath):
        flash('压缩文件创建失败。', 'error')
        return redirect(url_for('script_management'))

    # 发送文件给用户
    return send_file(zip_filepath, as_attachment=True)


@app.route('/preview/<filename>')
@login_required
def preview_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    app.logger.info(f"预览文件路径: {file_path}")  # 日志输出路径信息
    if os.path.exists(file_path) and allowed_file(filename):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return render_template('preview.html', filename=filename, content=content)
    else:
        flash('文件不存在或文件类型不支持预览。', 'error')
        return redirect(url_for('index'))


@app.route('/edit/<filename>', methods=['GET', 'POST'])
@login_required
def edit_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not allowed_edit_file(filename):
        flash('文件类型不支持编辑。', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_content = request.form['content'].replace('\r\n', '\n')

        # 可以在这里加入内容检查，避免保存恶意内容
        if "<script>" in new_content:
            flash('保存失败：文件内容包含非法字符。', 'error')
            return redirect(url_for('edit_file', filename=filename))

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(new_content)
        flash(f'文件 {filename} 已成功更新！', 'success')
        return redirect(url_for('edit_file', filename=filename))

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read().replace('\r\n', '\n')
        return render_template('edit.html', filename=filename, content=content)
    else:
        flash('文件不存在。', 'error')
        return redirect(url_for('edit_file', filename=filename))


@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    job_id = request.form['job_id']
    script_name = request.form['script_name']

    # 获取天、小时、分钟和秒，并转换为总秒数
    interval_days = int(request.form['interval_days'])
    interval_hours = int(request.form['interval_hours'])
    interval_minutes = int(request.form['interval_minutes'])
    interval_seconds = int(request.form['interval_seconds'])

    total_seconds = (interval_days * 86400) + (interval_hours * 3600) + (interval_minutes * 60) + interval_seconds

    remark = request.form.get('remark', '')
    from models import add_task
    try:
        add_task(scheduler, job_id, script_name, total_seconds, remark)
        flash(f'任务 {job_id} ({script_name}) 添加成功！', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('index'))


@app.route('/batch_delete_tasks', methods=['POST'])
@login_required
def batch_delete_tasks():
    from models import remove_task
    selected_tasks = request.form.get('selected_tasks')
    if selected_tasks:
        task_ids = selected_tasks.split(',')
        for job_id in task_ids:
            try:
                remove_task(scheduler, job_id)
                flash(f'任务 {job_id} 已删除！', 'success')
            except Exception as e:
                flash(f'删除任务 {job_id} 时出错: {str(e)}', 'danger')
    else:
        flash('未选择任何任务。', 'warning')
    return redirect(url_for('index'))


@app.route('/batch_pause_tasks', methods=['POST'])
@login_required
def batch_pause_tasks():
    from models import pause_task
    selected_tasks = request.form.get('selected_tasks')
    if selected_tasks:
        task_ids = selected_tasks.split(',')
        for job_id in task_ids:
            try:
                pause_task(scheduler, job_id)
                flash(f'任务 {job_id} 已暂停！', 'success')
            except Exception as e:
                flash(f'暂停任务 {job_id} 时出错: {str(e)}', 'danger')
    else:
        flash('未选择任何任务。', 'warning')
    return redirect(url_for('index'))


@app.route('/batch_resume_tasks', methods=['POST'])
@login_required
def batch_resume_tasks():
    from models import resume_task
    selected_tasks = request.form.get('selected_tasks')
    if selected_tasks:
        task_ids = selected_tasks.split(',')
        for job_id in task_ids:
            try:
                resume_task(scheduler, job_id)
                flash(f'任务 {job_id} 已恢复！', 'success')
            except Exception as e:
                flash(f'恢复任务 {job_id} 时出错: {str(e)}', 'danger')
    else:
        flash('未选择任何任务。', 'warning')
    return redirect(url_for('index'))


@app.route('/update_task', methods=['POST'])
@login_required
def update_task():
    job_id = request.form['job_id']

    # 获取天、小时、分钟和秒，并转换为总秒数
    interval_days = int(request.form['interval_days'])
    interval_hours = int(request.form['interval_hours'])
    interval_minutes = int(request.form['interval_minutes'])
    interval_seconds = int(request.form['interval_seconds'])

    total_seconds = (interval_days * 86400) + (interval_hours * 3600) + (interval_minutes * 60) + interval_seconds

    from models import update_task_interval
    try:
        update_task_interval(scheduler, job_id, total_seconds)
        flash(f'本次执行结束后，下次执行 任务{job_id} 的间隔更新为 {total_seconds} 秒！', 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('index'))


@app.route('/logs/<job_id>')
@login_required
def view_logs(job_id):
    log_file_path = os.path.join('logs', f'{job_id}.log')
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as log_file:
            logs = log_file.read()
    else:
        logs = '没有找到相关日志。'

    return render_template('logs.html', job_id=job_id, logs=logs)


@app.route('/clear_logs/<job_id>', methods=['POST'])
@login_required
def clear_logs(job_id):
    try:
        # 你的日志清理逻辑，例如删除日志文件或清空日志内容
        log_file_path = f'logs/{job_id}.log'
        with open(log_file_path, 'w') as log_file:
            log_file.write('')

        flash('日志已清理成功', 'success')
    except Exception as e:
        flash(f'清理日志时出错: {str(e)}', 'danger')

    return redirect(url_for('view_logs', job_id=job_id))


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
