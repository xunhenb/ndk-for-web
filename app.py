import os
import zipfile
import subprocess
import uuid
import shutil
import time
import sys
import threading
from flask import Flask, request, send_file, jsonify, render_template
from flask_cors import CORS

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})

NDK_PATH = r"C:\wwwroot\120.26.126.144\so\templates\android-ndk-r27d"
UPLOAD_FOLDER = r"C:\wwwroot\120.26.126.144\so\uploads"
ALLOWED_EXTENSIONS = {'zip'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024 

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['PROPAGATE_EXCEPTIONS'] = True

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

start_time = time.time()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup_old_files():
   
    try:
        now = time.time()
        for item in os.listdir(UPLOAD_FOLDER):
            item_path = os.path.join(UPLOAD_FOLDER, item)
            if os.path.isdir(item_path):
                if now - os.path.getmtime(item_path) > 3600:  
                    try:
                        shutil.rmtree(item_path)
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 清理过期文件夹: {item_path}")
                    except:
                        pass
    except Exception as e:
        print(f"清理过程出错: {e}")

def auto_cleanup_thread():
  
    while True:
        time.sleep(1800)  
        try:
            cleanup_old_files()
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 自动清理完成")
        except Exception as e:
            print(f"自动清理失败: {e}")

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        return f"模板加载失败: {str(e)}", 500

@app.route('/ping')
def ping():
    
    return jsonify({
        "status": "alive",
        "time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "uptime": int(time.time() - start_time)
    }), 200

@app.route('/test')
def test():
   
    return jsonify({
        "status": "ok",
        "message": "服务器运行正常",
        "time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "uptime": int(time.time() - start_time),
        "ndk_exists": os.path.exists(NDK_PATH),
        "ndk_build_exists": os.path.exists(os.path.join(NDK_PATH, "ndk-build.cmd")) if os.path.exists(NDK_PATH) else False
    })

@app.route('/compile', methods=['POST', 'OPTIONS'])
def compile_ndk():
   
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, X-Requested-With')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response, 200
    
   
    request_id = str(uuid.uuid4())[:8]
    print(f"\n[{time.strftime('%H:%M:%S')}][{request_id}] 开始处理编译请求")
    
    try:
        
        if not os.path.exists(NDK_PATH):
            return jsonify({"error": f"NDK路径不存在: {NDK_PATH}"}), 500
        
      
        if 'file' not in request.files:
            return jsonify({"error": "没有文件部分"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "没有选择文件"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": "只支持ZIP压缩包"}), 400

     
        work_id = str(uuid.uuid4())
        work_path = os.path.join(app.config['UPLOAD_FOLDER'], work_id)
        zip_path = os.path.join(work_path, "source.zip")
        os.makedirs(work_path, exist_ok=True)
        
      
        file.save(zip_path)
        print(f"[{request_id}] 文件已保存: {zip_path}")
        
     
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(work_path)
            print(f"[{request_id}] 解压完成")
        except Exception as e:
            return jsonify({"error": f"解压失败: {str(e)}"}), 400
        
       
        has_jni = os.path.exists(os.path.join(work_path, 'jni'))
        has_android_mk = os.path.exists(os.path.join(work_path, 'Android.mk')) or \
                        os.path.exists(os.path.join(work_path, 'jni', 'Android.mk'))
        
        if not has_jni and not has_android_mk:
            return jsonify({
                "error": "无效的项目结构",
                "log": "ZIP包需要包含 jni/ 文件夹和 Android.mk"
            }), 400
        
    
        ndk_build = os.path.join(NDK_PATH, "ndk-build.cmd")
        build_cmd = f'cd /d "{work_path}" && "{ndk_build}"'
        
        print(f"[{request_id}] 执行: {build_cmd}")
        
        try:
            result = subprocess.run(
                build_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                encoding='gbk'
            )
            
            print(f"[{request_id}] 编译完成，返回码: {result.returncode}")
            
        except subprocess.TimeoutExpired:
            return jsonify({"error": "编译超时（超过120秒）"}), 500
        except Exception as e:
            return jsonify({"error": f"编译执行失败: {str(e)}"}), 500
        
     
        if result.returncode == 0:
         
            so_files = []
            for root, dirs, files in os.walk(work_path):
                for file in files:
                    if file.endswith('.so'):
                        file_path = os.path.join(root, file)
                        so_files.append({
                            'path': file_path,
                            'name': file,
                            'abi': os.path.basename(os.path.dirname(file_path)) if 'libs' in file_path else 'unknown'
                        })
                        print(f"[{request_id}] 找到so: {file}")
            
            if not so_files:
                return jsonify({
                    "warning": "编译成功但未找到so文件",
                    "log": result.stdout
                }), 200
            
         
            if len(so_files) == 1:
                so_file = so_files[0]
                print(f"[{request_id}] 返回单个so文件: {so_file['name']}")
                
                return send_file(
                    so_file['path'],
                    as_attachment=True,
                    download_name=so_file['name'],
                    mimetype='application/octet-stream'
                )
            
     
            else:
                print(f"[{request_id}] 发现多个so文件: {len(so_files)}个")
                
             
                file_list = []
                for sf in so_files:
                    file_list.append({
                        'name': sf['name'],
                        'abi': sf['abi'],
                        'size': os.path.getsize(sf['path']),
                        'path': sf['path']
                    })
                
              
                return jsonify({
                    "multiple_files": True,
                    "files": file_list,
                    "message": f"发现 {len(so_files)} 个so文件，请选择要下载的文件",
                    "work_id": work_id
                }), 200
        else:
         
            error_log = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            return jsonify({
                "error": "编译失败",
                "log": error_log
            }), 400
            
    except Exception as e:
        print(f"[{request_id}] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500

@app.route('/download/<work_id>/<filename>')
def download_file(work_id, filename):
    
    try:
        file_path = os.path.join(UPLOAD_FOLDER, work_id, filename)
        
      
        if not os.path.exists(file_path):
            for root, dirs, files in os.walk(os.path.join(UPLOAD_FOLDER, work_id)):
                if filename in files:
                    file_path = os.path.join(root, filename)
                    break
        
        if not os.path.exists(file_path):
            return jsonify({"error": "文件不存在"}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/stats')
def stats():
   
    try:
      
        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            file_count += len(files)
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        
        return jsonify({
            "uptime": int(time.time() - start_time),
            "upload_folder_size": total_size,
            "upload_file_count": file_count,
            "ndk_exists": os.path.exists(NDK_PATH)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*70)
    print("  NDK打包服务启动 by 逊和 (多线程版)")
    print("="*70)
    print(f"  NDK路径: {NDK_PATH}")
    print(f"  NDK存在: {os.path.exists(NDK_PATH)}")
    print(f"  上传目录: {UPLOAD_FOLDER}")
    print(f"  访问地址: http://120.26.126.144:5000")
    print(f"  心跳地址: http://120.26.126.144:5000/ping")
    print(f"  状态地址: http://120.26.126.144:5000/stats")
    print("="*70)
    print("  自动清理: 每30分钟")
    print(" 并发处理: 支持多线程")
    print("  提示: 按 Ctrl+C 安全退出")
    print("="*70 + "\n")
    
  
    cleanup_old_files()
    
   
    cleanup_thread = threading.Thread(target=auto_cleanup_thread, daemon=True)
    cleanup_thread.start()
    print(" 自动清理线程已启动")
    
   
    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True,     
            processes=1        
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  收到退出信号，正在关闭服务器...")
        time.sleep(1)
        print(" 服务器已关闭")