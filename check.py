#!/usr/bin/env python3
# github_poller.py
import requests
import subprocess
import time
import json
import logging
import os
import sys
from datetime import datetime
import argparse


class GitHubAutoUpdater:
    def __init__(self, config):
        self.owner = config['owner']
        self.repo = config['repo']
        self.branch = config.get('branch', 'main')
        self.project_path = config['project_path']
        self.poll_interval = config.get('poll_interval', 60)  # 默认5分钟
        self.github_token = config.get('github_token')
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay', 10)

        # 设置日志
        self.setup_logging(config.get('log_file', '/home/admin/test/github_poller.log'))

        # 初始化状态
        self.last_commit = self.get_local_commit()
        self.update_count = 0
        self.last_check = None

    def setup_logging(self, log_file):
        """配置日志系统"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger('GitHubPoller')

    def get_headers(self):
        """获取API请求头"""
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        return headers

    def get_local_commit(self):
        """获取本地最新commit hash"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            commit_hash = result.stdout.strip()
            self.logger.debug(f"本地commit: {commit_hash[:8]}")
            return commit_hash
        except subprocess.CalledProcessError as e:
            self.logger.error(f"获取本地commit失败: {e.stderr}")
            return None
        except Exception as e:
            self.logger.error(f"获取本地commit异常: {e}")
            return None

    def get_remote_commit_info(self):
        """获取远程仓库最新commit信息"""
        url = f"https://20.205.243.168/repos/{self.owner}/{self.repo}/branches/{self.branch}"

        try:
            response = requests.get(url, headers=self.get_headers(), timeout=10)

            if response.status_code == 200:
                data = response.json()
                commit = data['commit']
                return {
                    'sha': commit['sha'],
                    'message': commit['commit']['message'],
                    'author': commit['commit']['author']['name'],
                    'date': commit['commit']['author']['date'],
                    'url': commit['html_url']
                }
            elif response.status_code == 404:
                self.logger.error(f"分支不存在: {self.branch}")
            elif response.status_code == 403:
                self.logger.warning("API速率限制，考虑使用GitHub Token")
            else:
                self.logger.error(f"API请求失败: {response.status_code}")

        except requests.RequestException as e:
            self.logger.error(f"网络请求异常: {e}")

        return None

    def has_update_available(self):
        """检查是否有可用更新"""
        self.last_check = datetime.now()

        remote_commit_info = self.get_remote_commit_info()
        if not remote_commit_info:
            return False, None

        remote_commit = remote_commit_info['sha']
        local_commit = self.get_local_commit()

        if not local_commit:
            self.logger.warning("无法获取本地commit，跳过检查")
            return False, remote_commit_info

        # 比较commit hash
        if remote_commit != local_commit:
            self.logger.info(f"检测到更新: {local_commit[:8]} -> {remote_commit[:8]}")
            self.logger.info(f"提交信息: {remote_commit_info['message']}")
            return True, remote_commit_info

        self.logger.debug("没有检测到更新")
        return False, remote_commit_info

    def fetch_latest_code(self):
        """获取最新代码"""
        commands = [
            'git fetch origin',
            f'git checkout {self.branch}',
            f'git reset --hard origin/{self.branch}'
        ]

        for i, cmd in enumerate(commands):
            for attempt in range(self.max_retries):
                try:
                    self.logger.info(f"执行命令: {cmd} (尝试 {attempt + 1}/{self.max_retries})")

                    result = subprocess.run(
                        cmd,
                        shell=True,
                        cwd=self.project_path,
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=60
                    )

                    self.logger.debug(f"命令输出: {result.stdout}")
                    if result.stderr:
                        self.logger.debug(f"命令错误输出: {result.stderr}")

                    break  # 成功则跳出重试循环

                except subprocess.CalledProcessError as e:
                    self.logger.error(f"命令执行失败: {e.stderr}")
                    if attempt == self.max_retries - 1:
                        return False
                    time.sleep(self.retry_delay)
                except subprocess.TimeoutExpired:
                    self.logger.error("命令执行超时")
                    if attempt == self.max_retries - 1:
                        return False
                    time.sleep(self.retry_delay)

        return True

    def install_dependencies(self):
        """安装依赖"""
        requirements_file = os.path.join(self.project_path, 'requirements.txt')

        if os.path.exists(requirements_file):
            self.logger.info("安装Python依赖...")

            for attempt in range(self.max_retries):
                try:
                    result = subprocess.run(
                        ['pip', 'install', '-r', 'requirements.txt'],
                        cwd=self.project_path,
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=300
                    )

                    self.logger.info("依赖安装成功")
                    self.logger.debug(f"安装输出: {result.stdout}")
                    return True

                except subprocess.CalledProcessError as e:
                    self.logger.error(f"依赖安装失败: {e.stderr}")
                    if attempt == self.max_retries - 1:
                        return False
                    time.sleep(self.retry_delay)
                except subprocess.TimeoutExpired:
                    self.logger.error("依赖安装超时")
                    if attempt == self.max_retries - 1:
                        return False
                    time.sleep(self.retry_delay)

        else:
            self.logger.info("未找到requirements.txt，跳过依赖安装")
            return True

    def run_custom_scripts(self):
        """运行自定义部署脚本"""
        scripts = [
            {'name': '数据库迁移', 'command': 'python manage.py migrate', 'check_file': 'manage.py'},
            {'name': '静态文件收集', 'command': 'python manage.py collectstatic --noinput', 'check_file': 'manage.py'},
            {'name': '单元测试', 'command': 'python -m pytest tests/', 'check_file': 'pytest.ini'}
        ]

        for script in scripts:
            check_file = os.path.join(self.project_path, script['check_file'])
            if os.path.exists(check_file):
                self.logger.info(f"执行{script['name']}...")

                try:
                    result = subprocess.run(
                        script['command'],
                        shell=True,
                        cwd=self.project_path,
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=120
                    )
                    self.logger.info(f"{script['name']}执行成功")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    self.logger.warning(f"{script['name']}执行失败: {e}")

    def restart_application(self):
        """重启应用服务"""
        services = ['myservice', 'nginx', 'gunicorn']

        for service in services:
            try:
                # 检查服务是否存在
                result = subprocess.run(
                    ['systemctl', 'status', service],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    self.logger.info(f"重启服务: {service}")
                    subprocess.run(
                        ['sudo', 'systemctl', 'restart', service],
                        check=True,
                        timeout=30
                    )
                    self.logger.info(f"服务 {service} 重启成功")

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                self.logger.error(f"服务 {service} 重启失败: {e}")

    def create_backup(self):
        """创建备份"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = f"/backup/{self.repo}_{timestamp}"

            self.logger.info(f"创建备份: {backup_dir}")
            subprocess.run(
                ['cp', '-r', self.project_path, backup_dir],
                check=True
            )
            return True
        except Exception as e:
            self.logger.error(f"备份创建失败: {e}")
            return False

    def perform_update(self, commit_info):
        """执行完整的更新流程"""
        self.logger.info("开始执行更新流程...")

        # 1. 创建备份
        if not self.create_backup():
            self.logger.warning("备份失败，继续更新流程")

        # 2. 获取最新代码
        if not self.fetch_latest_code():
            self.logger.error("代码更新失败")
            return False

        # 3. 安装依赖
        if not self.install_dependencies():
            self.logger.error("依赖安装失败")
            return False

        # 4. 运行自定义脚本
        self.run_custom_scripts()

        # 5. 重启应用
        self.restart_application()

        # 6. 更新本地commit记录
        self.last_commit = commit_info['sha']
        self.update_count += 1

        self.logger.info(f"更新完成! 总共更新次数: {self.update_count}")
        return True

    def send_notification(self, commit_info, success=True):
        """发送通知（可扩展为邮件、钉钉、微信等）"""
        status = "成功" if success else "失败"
        message = f"""
项目: {self.owner}/{self.repo}
分支: {self.branch}
更新: {status}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
提交: {commit_info['message']}
作者: {commit_info['author']}
Commit: {commit_info['sha'][:8]}
        """

        self.logger.info(f"更新通知:\n{message}")
        # 这里可以添加邮件、Webhook等通知方式

    def run(self):
        """主运行循环"""
        self.logger.info("GitHub自动更新器启动")
        self.logger.info(f"监控仓库: {self.owner}/{self.repo} 分支: {self.branch}")
        self.logger.info(f"项目路径: {self.project_path}")
        self.logger.info(f"检查间隔: {self.poll_interval}秒")

        try:
            while True:
                try:
                    has_update, commit_info = self.has_update_available()

                    if has_update and commit_info:
                        self.logger.info(f"开始处理更新: {commit_info['message']}")

                        success = self.perform_update(commit_info)
                        self.send_notification(commit_info, success)

                        if not success:
                            self.logger.error("更新失败，将在下次检查时重试")
                    else:
                        self.logger.info("GitHub没有更新的版本")
                    # 等待下一次检查
                    time.sleep(self.poll_interval)

                except KeyboardInterrupt:
                    self.logger.info("收到中断信号，停止运行")
                    break
                except Exception as e:
                    self.logger.error(f"主循环异常: {e}")
                    time.sleep(self.poll_interval)

        except Exception as e:
            self.logger.error(f"运行异常: {e}")
        finally:
            self.logger.info("GitHub自动更新器停止")


def load_config(config_file=None):
    """加载配置文件"""
    default_config = {
        'owner': 'zhizhi1hao',
        'repo': 'test',
        'branch': 'main',
        'project_path': '/home/admin/test',
        'poll_interval': 300,
        'github_token': os.getenv('GITHUB_TOKEN'),
        'log_file': '/home/admin/test/github_poller.log'
    }

    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            user_config = json.load(f)
            default_config.update(user_config)

    return default_config


def main():
    parser = argparse.ArgumentParser(description='GitHub自动更新器')
    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument('--once', action='store_true', help='只检查一次')
    parser.add_argument('--interval', '-i', type=int, help='检查间隔（秒）')

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    if args.interval:
        config['poll_interval'] = args.interval

    # 创建更新器实例
    updater = GitHubAutoUpdater(config)

    if args.once:
        # 单次检查模式
        has_update, commit_info = updater.has_update_available()
        if has_update:
            print(f"检测到更新: {commit_info['message']}")
            updater.perform_update(commit_info)
        else:
            print("没有检测到更新")
    else:
        # 持续运行模式
        updater.run()


if __name__ == "__main__":
    main()
