import time
import logging
import os
import sys
from datetime import datetime
from netmiko import ConnectHandler
from netmiko import NetMikoTimeoutException, NetMikoAuthenticationException
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# 获取资源文件的绝对路径，兼容 PyInstaller 打包环境
def resource_path(relative_path):
    """获取资源文件的绝对路径，兼容 PyInstaller 打包环境"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 配置日志
def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'syslog_config_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

class SyslogConfigurator:
    """Syslog配置器类"""
    
    def __init__(self, csv_file, loghost='10.40.29.201', max_workers=10, update_callback=None):
        self.csv_file = csv_file
        self.loghost = loghost
        self.max_workers = max_workers
        self.logger = setup_logging()
        self.results = {'success': [], 'failed': [], 'skipped': []}
        self.update_callback = update_callback  # 用于实时更新 UI
        self.device_type_mapping = {
            'huawei': 'huawei',
            'h3c': 'hp_comware',
            'ruijie': 'ruijie_os',
            'cisco': 'cisco_ios',
            'cisco_ios': 'cisco_ios',
            'cisco_xe': 'cisco_xe',
            'cisco_nxos': 'cisco_nxos',
            'arista': 'arista_eos',
            'juniper': 'juniper',
            'fortinet': 'fortinet',
            'paloalto': 'paloalto_panos'
        }
    
    def load_devices(self):
        """加载设备信息"""
        try:
            if not os.path.exists(self.csv_file):
                self.logger.error(f"找不到 Sinfo.csv 文件: {self.csv_file}")
                return False
            self.devices = pd.read_csv(self.csv_file)
            self.logger.info(f"成功加载 {len(self.devices)} 台设备信息")
            return True
        except FileNotFoundError:
            self.logger.error(f"找不到文件: {self.csv_file}")
            return False
        except Exception as e:
            self.logger.error(f"读取CSV文件失败: {e}")
            return False
    
    def validate_device_info(self, row):
        """验证设备信息完整性"""
        required_fields = ['Type', 'IP', 'ssh_type', 'User', 'Passwd']
        missing_fields = [field for field in required_fields if field not in row or pd.isna(row[field])]
        if missing_fields:
            self.logger.warning(f"设备 {row.get('IP', 'Unknown')} 缺少必要字段: {missing_fields}")
            return False
        return True
    
    def create_device_config(self, row):
        """创建设备连接配置"""
        device_type = row['ssh_type'].lower()
        netmiko_device_type = self.device_type_mapping.get(device_type, device_type)
        config = {
            'device_type': netmiko_device_type,
            'host': row['IP'],
            'username': row['User'],
            'password': row['Passwd'],
            'timeout': 30,
            'fast_cli': False,
            'global_delay_factor': 2
        }
        if netmiko_device_type in ['hp_comware', 'huawei']:
            config['global_delay_factor'] = 3
        elif netmiko_device_type == 'ruijie_os':
            config['global_delay_factor'] = 2
        elif netmiko_device_type in ['cisco_ios', 'cisco_xe']:
            config['fast_cli'] = True
        return config
    
    def generate_config_commands(self, host_ip, device_type):
        """生成配置命令"""
        device_type = device_type.lower()
        if device_type in ['huawei', 'h3c']:
            return [
                f"info-center loghost {self.loghost} source-ip {host_ip}",
                "info-center enable",
                "info-center console channel 6",
                "info-center console log level informational"
            ]
        elif device_type == 'ruijie':
            return [
                f"logging host {self.loghost}",
                "logging on",
                "logging console informational"
            ]
        elif device_type in ['cisco', 'cisco_ios', 'cisco_xe']:
            return [
                f"logging {self.loghost}",
                "logging console informational",
                "logging buffered informational"
            ]
        elif device_type == 'juniper':
            return [
                f"set system syslog host {self.loghost} any any",
                f"set system syslog host {self.loghost} facility local7",
                "commit"
            ]
        elif device_type == 'fortinet':
            return [
                f"config log syslogd setting",
                f"set server {self.loghost}",
                "set status enable",
                "end"
            ]
        else:
            return [
                f"info-center loghost {self.loghost} source-ip {host_ip}",
                "info-center enable",
                "info-center console channel 6",
                "info-center console log level informational"
            ]
    
    def verify_config(self, conn, host_ip, device_type):
        """验证配置是否生效"""
        device_type = device_type.lower()
        try:
            if device_type in ['huawei', 'h3c']:
                output = conn.send_command("display info-center")
                self.logger.info(f"验证输出: {output}")
                if self.loghost in output:
                    self.logger.info(f"找到日志服务器地址: {self.loghost}")
                    return True
            elif device_type == 'ruijie':
                output = conn.send_command("show logging")
                self.logger.info(f"验证输出: {output}")
                if self.loghost in output:
                    self.logger.info(f"找到日志服务器地址: {self.loghost}")
                    return True
            elif device_type in ['cisco', 'cisco_ios', 'cisco_xe']:
                output = conn.send_command("show logging")
                self.logger.info(f"验证输出: {output}")
                if self.loghost in output:
                    self.logger.info(f"找到日志服务器地址: {self.loghost}")
                    return True
            elif device_type == 'juniper':
                output = conn.send_command("show system syslog")
                self.logger.info(f"验证输出: {output}")
                if self.loghost in output:
                    self.logger.info(f"找到日志服务器地址: {self.loghost}")
                    return True
            elif device_type == 'fortinet':
                output = conn.send_command("get system syslog")
                self.logger.info(f"验证输出: {output}")
                if self.loghost in output:
                    self.logger.info(f"找到日志服务器地址: {self.loghost}")
                    return True
            else:
                output = conn.send_command("display info-center")
                self.logger.info(f"验证输出: {output}")
                if self.loghost in output:
                    self.logger.info(f"找到日志服务器地址: {self.loghost}")
                    return True
            try:
                config_output = conn.send_command("show running-config | include logging")
                if self.loghost in config_output:
                    self.logger.info(f"在配置中找到日志服务器地址: {self.loghost}")
                    return True
            except:
                pass
            self.logger.warning(f"未找到日志服务器地址: {self.loghost}")
            return False
        except Exception as e:
            self.logger.warning(f"验证配置失败 {host_ip}: {e}")
            return False
    
    def configure_device(self, row):
        """配置单个设备"""
        host_ip = row['IP']
        device_type = row['Type']
        if not self.validate_device_info(row):
            return {'status': 'skipped', 'ip': host_ip, 'message': '设备信息不完整'}
        try:
            device_config = self.create_device_config(row)
            self.logger.info(f"正在连接设备: {host_ip} ({device_type})")
            with ConnectHandler(**device_config) as conn:
                self.logger.info(f"[成功] 成功登录设备: {host_ip}")
                conn.enable()
                config_commands = self.generate_config_commands(host_ip, row['ssh_type'])
                config_output = conn.send_config_set(config_commands=config_commands)
                self.logger.info(f"[配置] {host_ip} 配置命令执行完成")
                save_output = conn.save_config()
                self.logger.info(f"[保存] {host_ip} 配置保存成功")
                if self.verify_config(conn, host_ip, row['ssh_type']):
                    self.logger.info(f"[验证] {host_ip} 配置验证成功")
                    return {'status': 'success', 'ip': host_ip, 'message': '配置成功'}
                else:
                    self.logger.warning(f"[警告] {host_ip} 配置验证失败")
                    return {'status': 'failed', 'ip': host_ip, 'message': '配置验证失败'}
        except NetMikoTimeoutException:
            error_msg = f"连接超时: {host_ip}"
            self.logger.error(error_msg)
            return {'status': 'failed', 'ip': host_ip, 'message': error_msg}
        except NetMikoAuthenticationException:
            error_msg = f"认证失败: {host_ip}"
            self.logger.error(error_msg)
            return {'status': 'failed', 'ip': host_ip, 'message': error_msg}
        except Exception as e:
            error_msg = f"设备 {host_ip} 处理失败: {str(e)}"
            self.logger.error(error_msg)
            return {'status': 'failed', 'ip': host_ip, 'message': error_msg}
    
    def run_configuration(self):
        """运行批量配置"""
        if not self.load_devices():
            return False
        self.logger.info("开始批量配置syslog...")
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for _, row in self.devices.iterrows():
                future = executor.submit(self.configure_device, row)
                futures.append(future)
                time.sleep(0.2)
            completed = 0
            total = len(futures)
            for future in as_completed(futures):
                result = future.result()
                completed += 1
                if result['status'] == 'success':
                    self.results['success'].append(result)
                elif result['status'] == 'failed':
                    self.results['failed'].append(result)
                else:
                    self.results['skipped'].append(result)
                if self.update_callback:
                    self.update_callback(completed, total, result)
        return self.print_summary(start_time)
    
    def print_summary(self, start_time):
        """打印执行结果汇总"""
        end_time = time.time()
        duration = end_time - start_time
        summary = "\n" + "="*60 + "\n"
        summary += "批量配置执行结果汇总\n"
        summary += "="*60 + "\n"
        summary += f"总耗时: {duration:.2f} 秒\n"
        summary += f"总设备数: {len(self.results['success']) + len(self.results['failed']) + len(self.results['skipped'])} 台\n"
        summary += f"成功配置: {len(self.results['success'])} 台\n"
        summary += f"配置失败: {len(self.results['failed'])} 台\n"
        summary += f"跳过设备: {len(self.results['skipped'])} 台\n"
        if self.results['success']:
            summary += f"\n✅ 成功配置的交换机 ({len(self.results['success'])} 台):\n"
            for i, result in enumerate(self.results['success'], 1):
                summary += f"  {i}. {result['ip']}\n"
        if self.results['failed']:
            summary += f"\n❌ 配置失败的交换机 ({len(self.results['failed'])} 台):\n"
            for i, result in enumerate(self.results['failed'], 1):
                summary += f"  {i}. {result['ip']} - 失败原因: {result['message']}\n"
        if self.results['skipped']:
            summary += f"\n⚠️ 跳过的交换机 ({len(self.results['skipped'])} 台):\n"
            for i, result in enumerate(self.results['skipped'], 1):
                summary += f"  {i}. {result['ip']} - 跳过原因: {result['message']}\n"
        total_processed = len(self.results['success']) + len(self.results['failed'])
        if total_processed > 0:
            success_rate = (len(self.results['success']) / total_processed) * 100
            summary += f"\n📊 配置成功率: {success_rate:.1f}% ({len(self.results['success'])}/{total_processed})\n"
        summary += "="*60
        return summary

class SyslogApp:
    """Syslog 配置图形界面"""
    def __init__(self, root):
        self.root = root
        self.root.title("Syslog 批量配置工具")
        self.root.geometry("600x450")
        self.root.configure(bg="#E0F7FA")  # 淡蓝色背景
        self.root.resizable(False, False)
        
        # 样式配置
        self.style = ttk.Style()
        self.style.configure("TButton", font=("Arial", 12), padding=10, background="#4B5EAA")
        self.style.configure("TLabel", font=("Arial", 12), background="#E0F7FA")
        self.style.configure("TEntry", font=("Arial", 12))
        self.style.configure("TFrame", background="#E0F7FA")
        
        # 主框架
        self.main_frame = ttk.Frame(self.root, padding=20)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        
        # CSV 文件路径输入框
        self.csv_path_var = tk.StringVar(value=resource_path("Sinfo.csv"))
        ttk.Label(self.main_frame, text="Sinfo.csv 文件路径:").grid(row=0, column=0, sticky="w", pady=5)
        self.csv_entry = ttk.Entry(self.main_frame, textvariable=self.csv_path_var, width=40)
        self.csv_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        ttk.Button(self.main_frame, text="浏览", command=self.browse_file).grid(row=1, column=1, sticky="w")
        
        # 日志服务器地址输入框
        self.loghost_var = tk.StringVar(value="10.40.29.201")
        ttk.Label(self.main_frame, text="日志服务器地址:").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(self.main_frame, textvariable=self.loghost_var, width=40).grid(row=3, column=0, sticky="ew", padx=(0, 10))
        
        # 最大线程数输入框
        self.max_workers_var = tk.StringVar(value="10")
        ttk.Label(self.main_frame, text="最大线程数:").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(self.main_frame, textvariable=self.max_workers_var, width=40).grid(row=5, column=0, sticky="ew", padx=(0, 10))
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=6, column=0, columnspan=2, sticky="ew", pady=10)
        
        # 运行和导出按钮
        self.run_button = ttk.Button(self.main_frame, text="运行配置", command=self.run_config)
        self.run_button.grid(row=7, column=0, sticky="w", pady=10)
        self.export_button = ttk.Button(self.main_frame, text="导出结果", command=self.export_results, state="disabled")
        self.export_button.grid(row=7, column=1, sticky="e", pady=10)
        
        # 结果显示区域（带滚动条）
        self.result_frame = ttk.Frame(self.main_frame)
        self.result_frame.grid(row=8, column=0, columnspan=2, sticky="nsew")
        self.result_text = tk.Text(self.result_frame, height=12, width=60, font=("Arial", 10), bg="#FFFFFF", fg="#000000")
        self.result_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self.result_frame, orient="vertical", command=self.result_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.result_text.config(yscrollcommand=scrollbar.set)
        self.result_text.insert(tk.END, "配置结果将显示在这里...\n")
        self.result_text.config(state="disabled")
        
        # 配置颜色标签
        self.result_text.tag_configure("success", foreground="#2E7D32")  # 绿色
        self.result_text.tag_configure("failed", foreground="#D32F2F")   # 红色
        self.result_text.tag_configure("skipped", foreground="#F57C00")  # 橙色
        self.result_text.tag_configure("summary", foreground="#4B5EAA")  # 灰蓝色
        
        # 设置权重
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(8, weight=1)
        self.result_frame.columnconfigure(0, weight=1)
        self.result_frame.rowconfigure(0, weight=1)
        
        self.results_summary = ""  # 存储结果以便导出
    
    def browse_file(self):
        """打开文件选择对话框"""
        file_path = filedialog.askopenfilename(filetypes=[("CSV 文件", "*.csv")])
        if file_path:
            self.csv_path_var.set(file_path)
    
    def update_progress(self, completed, total, result):
        """实时更新进度和结果"""
        self.progress_var.set((completed / total) * 100)
        self.result_text.config(state="normal")
        tag = result['status']
        self.result_text.insert(tk.END, f"{result['ip']} - {result['message']}\n", tag)
        self.result_text.see(tk.END)
        self.result_text.config(state="disabled")
        self.root.update()
    
    def export_results(self):
        """导出结果到文件"""
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("文本文件", "*.txt")])
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.results_summary)
                messagebox.showinfo("成功", f"结果已导出到 {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {str(e)}")
    
    def run_config(self):
        """运行 syslog 配置"""
        csv_file = self.csv_path_var.get()
        loghost = self.loghost_var.get()
        try:
            max_workers = int(self.max_workers_var.get())
            if max_workers <= 0:
                messagebox.showerror("错误", "最大线程数必须为正整数！")
                return
        except ValueError:
            messagebox.showerror("错误", "请输入有效的最大线程数！")
            return
        
        if not csv_file:
            messagebox.showerror("错误", "请选择 Sinfo.csv 文件！")
            return
        if not loghost:
            messagebox.showerror("错误", "请输入日志服务器地址！")
            return
        
        self.run_button.config(state="disabled")
        self.export_button.config(state="disabled")
        self.result_text.config(state="normal")
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "正在运行配置...\n", "summary")
        self.result_text.config(state="disabled")
        self.progress_var.set(0)
        self.root.update()
        
        try:
            configurator = SyslogConfigurator(csv_file, loghost, max_workers, self.update_progress)
            self.results_summary = configurator.run_configuration()
            self.result_text.config(state="normal")
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, self.results_summary, "summary")
            self.result_text.config(state="disabled")
            self.run_button.config(state="normal")
            self.export_button.config(state="normal")
            messagebox.showinfo("完成", "配置已完成，结果已显示！")
        except Exception as e:
            self.result_text.config(state="normal")
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"运行时发生错误: {str(e)}\n", "failed")
            self.result_text.config(state="disabled")
            self.run_button.config(state="normal")
            messagebox.showerror("错误", f"运行时发生错误: {str(e)}")

def main():
    """主函数"""
    root = tk.Tk()
    app = SyslogApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
