"""
WebSocket服务器模块，用于实时推送Agent状态信息
"""
from flask_socketio import SocketIO, emit
import json
import os
import time
import logging
from typing import Dict, Any, Optional
from threading import Lock

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketServer:
    """WebSocket服务器类，负责管理连接和消息推送"""

    def __init__(self, app=None):
        self.socketio = None
        self.app = app
        self.pid = os.getpid()
        self.connected_clients = set()
        self.status_cache = {}
        self.thinking_cache = {}
        self.lock = Lock()

        if app:
            self.init_app(app)

    def init_app(self, app):
        """初始化Flask-SocketIO"""
        self.app = app  # 设置Flask应用引用
        self.pid = os.getpid()
        self.socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            # 重要：当前系统大量使用 threading.Thread 在后台执行特征搜索/LLM 调用。
            # eventlet 模式下从“原生线程”里 emit 容易出现客户端收不到的情况（尤其是需要刷新才看到）。
            # 使用 threading 模式可保证跨线程 emit 行为可靠。
            async_mode='threading',
            logger=False,
            engineio_logger=False,
            ping_timeout=120,  # 加长ping超时，降低误判断线
            ping_interval=40,  # 加长ping间隔，减少心跳压力
            http_open_timeout=60  # HTTP连接超时
        )
        self.setup_handlers()
        logger.info(f"WebSocket server initialized (pid={self.pid})")

    def setup_handlers(self):
        """设置WebSocket事件处理器"""

        @self.socketio.on('connect')
        def handle_connect():
            """处理客户端连接"""
            try:
                client_id = request.sid
                self.connected_clients.add(client_id)
                logger.info(f"Client connected: {client_id} (pid={self.pid})")

                # 发送连接确认
                emit('status', {
                    'type': 'connection',
                    'message': 'Connected to ADDA WebSocket Server',
                    'timestamp': time.time()
                })

                # 发送当前缓存的状态
                self.send_cached_status()
                # 发送最近的思考消息
                self.send_cached_thinking()
            except Exception as e:
                logger.error(f"Error in handle_connect: {e}")

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """处理客户端断开连接"""
            try:
                client_id = request.sid
                self.connected_clients.discard(client_id)
                logger.info(f"Client disconnected: {client_id}")
            except Exception as e:
                logger.error(f"Error in handle_disconnect: {e}")

        @self.socketio.on('subscribe_agent')
        def handle_subscribe_agent(data):
            """处理订阅特定Agent状态"""
            agent = data.get('agent')
            if agent:
                emit('status', {
                    'type': 'subscription',
                    'message': f'Subscribed to {agent} status updates',
                    'timestamp': time.time()
                })
                logger.info(f"Client subscribed to agent: {agent}")

        @self.socketio.on('ping')
        def handle_ping():
            """处理心跳检测"""
            emit('pong', {'timestamp': time.time()})

    def send_agent_status(self, status_data: Dict[str, Any]):
        """发送Agent状态更新到所有连接的客户端"""
        try:
            agent = status_data.get('agent', 'unknown')
            status = status_data.get('status', 'unknown')
            work_type = status_data.get('work_type', 'N/A')

            print(f"\033[91m[WS SERVER STATUS] pid={self.pid} recv agent={agent} status={status} work_type={work_type}\033[0m")
            logger.info(f"WebSocket received agent status: {agent} = {status} ({work_type})")

            with self.lock:
                # 添加时间戳
                status_data['timestamp'] = time.time()

                # 缓存状态
                if agent not in self.status_cache:
                    self.status_cache[agent] = []

                # 保留最近50条状态记录
                self.status_cache[agent].append(status_data.copy())
                if len(self.status_cache[agent]) > 50:
                    self.status_cache[agent] = self.status_cache[agent][-50:]

                # 检查连接数
                client_count = len(self.connected_clients)
                print(f"\033[91m[WS SERVER STATUS] pid={self.pid} broadcasting to {client_count} clients agent={agent}\033[0m")

                # 广播状态更新
                self.socketio.emit('agent_status_update', status_data)
                print(f"\033[91m[WS SERVER STATUS] pid={self.pid} broadcasted agent={agent} status={status}\033[0m")
                logger.info(f"WebSocket broadcasted agent status: {agent} = {status}")

        except Exception as e:
            print(f"[WS ERROR] Error sending agent status: {e}")
            logger.error(f"Error sending agent status: {e}")

    def send_agent_thinking(self, thinking_data: Dict[str, Any]):
        """发送Agent思考过程到所有连接的客户端"""
        try:
            with self.lock:
                # 添加时间戳
                thinking_data['timestamp'] = time.time()

                # 缓存思考内容，便于短暂掉线后恢复
                agent = thinking_data.get('agent', 'unknown')
                if agent not in self.thinking_cache:
                    self.thinking_cache[agent] = []
                self.thinking_cache[agent].append(thinking_data.copy())
                # 保留最近50条思考
                if len(self.thinking_cache[agent]) > 50:
                    self.thinking_cache[agent] = self.thinking_cache[agent][-50:]

                print(f"\033[91m[WS SERVER THINK] pid={self.pid} broadcasting agent={agent} len={len(thinking_data.get('thinking',''))}\033[0m")
                # 广播思考过程
                self.socketio.emit('agent_thinking', thinking_data)

                logger.debug(f"Sent agent thinking: {thinking_data.get('agent', 'unknown')}")

        except Exception as e:
            logger.error(f"Error sending agent thinking: {e}")

    def send_cached_thinking(self, limit_per_agent: int = 5):
        """发送缓存的思考消息（防止掉线期间丢失）"""
        try:
            for agent, messages in self.thinking_cache.items():
                if not messages:
                    continue
                # 只补发最近几条，避免刷屏
                for message in messages[-limit_per_agent:]:
                    # 复制并刷新时间戳，避免前端因“过期”丢弃
                    msg = message.copy()
                    msg['timestamp'] = time.time()
                    print(f"\033[91m[WS SERVER THINK] pid={self.pid} replay cached agent={agent} len={len(message.get('thinking',''))}\033[0m")
                    self.socketio.emit('agent_thinking', msg)
                    logger.info(f"Sent cached thinking for agent: {agent}")
        except Exception as e:
            logger.error(f"Error sending cached thinking: {e}")

    def send_system_notification(self, notification: Dict[str, Any]):
        """发送系统通知到所有连接的客户端"""
        try:
            with self.lock:
                # 添加时间戳
                notification['timestamp'] = time.time()

                # 广播系统通知
                self.socketio.emit('system_notification', notification)

                logger.info(f"Sent system notification: {notification.get('message', 'unknown')}")

        except Exception as e:
            logger.error(f"Error sending system notification: {e}")

    def send_cached_status(self):
        """发送缓存的状态到新连接的客户端"""
        try:
            for agent, statuses in self.status_cache.items():
                if statuses:
                    # 发送该Agent的最新状态
                    latest_status = statuses[-1].copy()
                    latest_status['timestamp'] = time.time()
                    self.socketio.emit('agent_status_update', latest_status)
                    logger.info(f"Sent cached status for agent: {agent}")

        except Exception as e:
            logger.error(f"Error sending cached status: {e}")

    def clear_agent_cache(self, agent: Optional[str] = None):
        """清除Agent状态缓存"""
        with self.lock:
            if agent:
                self.status_cache.pop(agent, None)
                logger.info(f"Cleared cache for agent: {agent}")
            else:
                self.status_cache.clear()
                logger.info("Cleared all agent cache")
        # 同步清理思考缓存
        with self.lock:
            if agent:
                self.thinking_cache.pop(agent, None)
                logger.info(f"Cleared thinking cache for agent: {agent}")
            else:
                self.thinking_cache.clear()
                logger.info("Cleared all thinking cache")

    def get_connection_count(self):
        """获取当前连接的客户端数量"""
        return len(self.connected_clients)

    def run(self, host='0.0.0.0', port=5000, debug=False):
        """运行WebSocket服务器"""
        if self.socketio and self.app:
            self.socketio.run(
                self.app,
                host=host,
                port=port,
                debug=debug,
                use_reloader=False,
                allow_unsafe_werkzeug=True
            )
        else:
            logger.error("WebSocket server not initialized properly")
            if not self.app:
                logger.error("Flask app not set")
            if not self.socketio:
                logger.error("SocketIO not initialized")

# 延迟初始化WebSocket服务器实例
ws_server = None

def get_websocket_server():
    """获取WebSocket服务器实例（延迟初始化）"""
    global ws_server
    if ws_server is None:
        ws_server = WebSocketServer()
    return ws_server

# 导入request对象（需要在Flask上下文中）
from flask import request
