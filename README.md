# TimeTask

这是一个简单的定时任务调度器项目。使用 APScheduler 处理调度逻辑，支持定时运行多个 Python 文件，定时作业、预览编辑、实时暂停、日志服务等功能。

起因是自己写了很多 python 的自动化更新任务，又忘记每次及时更新，索性写了此服务方便自用，主要利用 flask 和 APScheduler 轻量级运行。


<img src="https://github.com/Chenyme/TimeTask/blob/main/public/home.png" alt="home">

## 功能和说明
<br>
<details>
  <summary><b>支持 py、sh、js、bat 运行</b></summary>
  <br>
    使用sh、js、bat脚本时请保证运行的设备有对应的环境，另外 py 脚本比较稳定，建议使用 py。
  <br>
  <img src="https://github.com/Chenyme/TimeTask/blob/main/public/file.png" alt="file">
</details>


<details>
  <summary><b>支持上传和编辑脚本</b></summary>
  <br>
    为了避免在服务器上上传和修改代码不方便，索性加了上传、预览和在线编辑的页面，编辑器用的 CodeMirror。由于引用了javascript，所以项目刚运行时初始化可能慢一点，大概几秒，耐心等待即可。
  <br>
  <img src="https://github.com/Chenyme/TimeTask/blob/main/public/edit.png" alt="edit">
</details>


<details>
<summary><b>支持暂停、继续、改时、查看</b></summary>
  <br>
  加入了暂停和继续功能，APScheduler不支持从上次暂停的的时间继续，于是加了一逻辑。然后也做了日志，比较建议在脚本内容中多用 try except + print 来记录情况，因为做了输出重定向，这样后期查看日志的时候能方便定位是否正常运行和运行情况。
  <br>
    <img src="https://github.com/Chenyme/TimeTask/blob/main/public/log.png" alt="log">
</details>
<br>


## 部署和运行

### 环境依赖
python > 3.6

### 本地运行
> 默认昵称：timetask
> 
> 默认密码：timetask

```python
# 克隆本项目
git clone https://github.com/Chenyme/TimeTask

# 安装依赖
pip install -r requirements.txt

# 直接运行
python app.py
```

### Docker运行
```shell
docker pull chenyme/timetask:0.1  # 拉取镜像

docker run -d \
    -e USERNAME=timetask \  # 修改你的默认昵称！！！
    -e PASSWORD=timetask \  # 修改你的默认密码！！！
    -e TZ=Asia/Shanghai \
    -p 5000:5000 \
    timetask
```
