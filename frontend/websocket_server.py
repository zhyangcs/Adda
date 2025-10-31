"""
WebSocket服务器模块，用于实时推送Agent状态信息
"""
from flask_socketio import SocketIO, emit
import json
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
        self.connected_clients = set()
        self.status_cache = {}
        self.lock = Lock()

        if app:
            self.init_app(app)

    def init_app(self, app):
        """初始化Flask-SocketIO"""
        self.app = app  # 设置Flask应用引用
        self.socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode='eventlet',
            logger=False,
            engineio_logger=False,
            ping_timeout=60,  # 60秒ping超时
            ping_interval=25,  # 25秒ping间隔
            http_open_timeout=60  # HTTP连接超时
        )
        self.setup_handlers()
        logger.info("WebSocket server initialized")

    def setup_handlers(self):
        """设置WebSocket事件处理器"""

        @self.socketio.on('connect')
        def handle_connect():
            """处理客户端连接"""
            try:
                client_id = request.sid
                self.connected_clients.add(client_id)
                logger.info(f"Client connected: {client_id}")

                # 发送连接确认
                emit('status', {
                    'type': 'connection',
                    'message': 'Connected to ADDA WebSocket Server',
                    'timestamp': time.time()
                })

                # 发送当前缓存的状态
                self.send_cached_status()
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

            print(f"[WS DEBUG] Received agent status: {agent} = {status} ({work_type})")
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
                print(f"[WS DEBUG] Broadcasting to {client_count} connected clients")

                # 广播状态更新
                self.socketio.emit('agent_status_update', status_data)
                print(f"[WS DEBUG] Broadcasted agent status: {agent} = {status}")
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

                # 广播思考过程
                self.socketio.emit('agent_thinking', thinking_data)

                logger.debug(f"Sent agent thinking: {thinking_data.get('agent', 'unknown')}")

        except Exception as e:
            logger.error(f"Error sending agent thinking: {e}")

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
                    latest_status = statuses[-1]
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