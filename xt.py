import socket
import subprocess
import time
import datetime
import os

HOST = "120.26.126.144"
PORT = 5000
CHECK_INTERVAL = 30 
LOG_FILE = "heartbeat.log"

WORK_DIR = r"C:\wwwroot\120.26.126.144\so"

def log(msg):
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except:
        pass

def check_port():
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((HOST, PORT))
        sock.close()
        return result == 0 
    except Exception as e:
        log(f"检测异常: {e}")
        return False

def start_app():
  
    log("端口关闭，正在启动 app.py...")
    try:
      
        subprocess.Popen(
            ["start", "cmd", "/c", "python app.py && pause"],
            cwd=WORK_DIR,
            shell=True
        )
        log("启动命令已执行")
        return True
    except Exception as e:
        log(f"启动失败: {e}")
        return False

def main():
    log("="*50)
    log("端口心跳检测启动")
    log(f"检测地址: {HOST}:{PORT}")
    log(f"检测间隔: {CHECK_INTERVAL}秒")
    log("="*50)
    
 
    if check_port():
        log("初始检测: 端口正常")
    else:
        log("初始检测: 端口关闭，尝试启动")
        start_app()
    
   
    while True:
        try:
           
            time.sleep(CHECK_INTERVAL)
            
          
            if check_port():
                log(f"检测: 端口正常")
            else:
                log(f"检测: 端口关闭，尝试重启")
                start_app()
                time.sleep(5) 
                
        except KeyboardInterrupt:
            log("用户中断，心跳检测停止")
            break
        except Exception as e:
            log(f"检测循环异常: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()