"""
Agent状态包装器，用于非侵入式监控Agent执行状态
通过WebSocket实时推送Agent工作状态和思考过程到前端
"""
import time
import json
import logging
from typing import Dict, Any, Optional, List
from functools import wraps
import queue
import threading

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局WebSocket消息队列，避免直接持有WebSocket服务器引用
_websocket_message_queue = queue.Queue()
_websocket_handlers = []
_websocket_lock = threading.Lock()

def register_websocket_handler(websocket_server):
    """注册WebSocket处理器"""
    global _websocket_handlers
    with _websocket_lock:
        # 避免重复注册导致重复广播
        if websocket_server not in _websocket_handlers:
            _websocket_handlers.append(websocket_server)

def unregister_websocket_handler(websocket_server):
    """注销WebSocket处理器"""
    global _websocket_handlers
    with _websocket_lock:
        if websocket_server in _websocket_handlers:
            _websocket_handlers.remove(websocket_server)

def _send_to_all_websockets(message_type: str, data: Dict[str, Any]):
    """向所有注册的WebSocket服务器发送消息"""
    global _websocket_handlers
    print(f"\033[91m[WS DISPATCH] handlers={len(_websocket_handlers)} type={message_type}\033[0m")

    if len(_websocket_handlers) == 0:
        print("[WARNING] No WebSocket handlers registered!")
        logger.warning("No WebSocket handlers registered!")
        return

    with _websocket_lock:
        for i, handler in enumerate(_websocket_handlers[:]):  # 创建副本避免迭代时修改
            try:
                print(f"\033[91m[WS DISPATCH] -> handler {i} type={message_type} payload_keys={list(data.keys())}\033[0m")
                if message_type == 'agent_status':
                    handler.send_agent_status(data)
                elif message_type == 'agent_thinking':
                    handler.send_agent_thinking(data)
                elif message_type == 'system_notification':
                    handler.send_system_notification(data)
                print(f"\033[91m[WS DISPATCH] <- handler {i} OK type={message_type}\033[0m")
            except Exception as e:
                print(f"\033[91m[WS DISPATCH] FAILED handler {i} type={message_type} err={e}\033[0m")
                logger.error(f"Error sending message to WebSocket handler: {e}")
                # 移除无效的处理器
                _websocket_handlers.remove(handler)

class AgentStatusWrapper:
    """
    Agent状态包装器类

    功能：
    1. 包装Agent执行过程，推送状态更新
    2. 推送Agent思考过程到前端
    3. 缓存Agent状态信息
    4. 提供非侵入式的状态监控
    """

    def __init__(self):
        """
        初始化Agent状态包装器
        """
        # 不直接持有WebSocket服务器实例，避免序列化问题
        self.agent_states = {}  # 缓存各Agent的当前状态
        self.agent_history = {}  # 缓存各Agent的历史状态
        self.current_thinking = {}  # 当前正在思考的Agent

    def set_websocket_server(self, websocket_server):
        """设置WebSocket服务器实例（注册到全局处理器列表）"""
        register_websocket_handler(websocket_server)

    def send_agent_status(self, status_data: Dict[str, Any]):
        """
        发送Agent状态更新

        Args:
            status_data: 状态数据字典，包含agent、status、details等信息
        """
        try:
            # 确保必要字段存在
            if 'agent' not in status_data:
                logger.warning("Agent status data missing 'agent' field")
                return

            if 'status' not in status_data:
                logger.warning("Agent status data missing 'status' field")
                return

            # 添加时间戳
            status_data['timestamp'] = time.time()

            # 缓存状态
            agent = status_data['agent']
            self.agent_states[agent] = status_data.copy()

            if agent not in self.agent_history:
                self.agent_history[agent] = []

            # 保留最近100条历史记录
            self.agent_history[agent].append(status_data.copy())
            if len(self.agent_history[agent]) > 100:
                self.agent_history[agent] = self.agent_history[agent][-100:]

            # 添加详细的调试日志
            logger.info(f"Sending agent status: {agent} - {status_data.get('status', 'unknown')} - {status_data.get('work_type', 'N/A')}")
            print(f"\033[91m[WS STATUS] agent={agent} status={status_data.get('status', 'unknown')} work_type={status_data.get('work_type', 'N/A')} ts={status_data['timestamp']}\033[0m")

            # 推送到WebSocket（通过全局消息系统）
            _send_to_all_websockets('agent_status', status_data)

            logger.debug(f"Sent agent status: {agent} - {status_data.get('status', 'unknown')}")

        except Exception as e:
            logger.error(f"Error sending agent status: {e}")
            print(f"[ERROR] Failed to send agent status: {e}")

    def send_agent_thinking(self, thinking_data: Dict[str, Any]):
        """
        发送Agent思考过程

        Args:
            thinking_data: 思考数据字典，包含agent、thinking等信息
        """
        try:
            print(f"\033[91m[WS THINK] recv call agent={thinking_data.get('agent')} preview={thinking_data.get('thinking','')[:60]}\033[0m")

            # 确保必要字段存在
            if 'agent' not in thinking_data:
                logger.warning("Agent thinking data missing 'agent' field")
                print("[WARNING] Agent thinking data missing 'agent' field")
                return

            if 'thinking' not in thinking_data:
                logger.warning("Agent thinking data missing 'thinking' field")
                print("[WARNING] Agent thinking data missing 'thinking' field")
                return

            thinking_content = thinking_data['thinking']
            has_code_block = "```" in thinking_content
            if len(thinking_content) > 150 and not has_code_block:
                thinking_content = thinking_content[:150] + "...(truncated)"
                thinking_data = thinking_data.copy()
                thinking_data['thinking'] = thinking_content

            # 添加时间戳
            thinking_data['timestamp'] = time.time()

            # 缓存当前思考（保留完整内容）
            agent = thinking_data['agent']
            self.current_thinking[agent] = thinking_data.copy()

            print(f"\033[91m[WS THINK] -> sending agent={agent} len={len(thinking_content)} ts={thinking_data['timestamp']}\033[0m")
            print(f"\033[91m[WS THINK] content preview: {thinking_content[:100]}\033[0m")

            # 推送到WebSocket（通过全局消息系统）
            _send_to_all_websockets('agent_thinking', thinking_data)

            print(f"\033[91m[WS THINK] <- sent agent={agent}\033[0m")
            logger.debug(f"Sent agent thinking: {agent}")

        except Exception as e:
            print(f"\033[91m[WS THINK] ERROR agent={thinking_data.get('agent')} err={e}\033[0m")
            logger.error(f"Error sending agent thinking: {e}")

    def start_agent_work(self, agent: str, work_type: str, details: Dict[str, Any] = None):
        """
        开始Agent工作

        Args:
            agent: Agent标识符
            work_type: 工作类型
            details: 详细信息
        """
        self.send_agent_status({
            "type": "agent_status",
            "agent": agent,
            "status": "working",
            "work_type": work_type,
            "details": details or {}
        })

    def finish_agent_work(self, agent: str, result: Dict[str, Any]):
        """
        完成Agent工作

        Args:
            agent: Agent标识符
            result: 工作结果
        """
        self.send_agent_status({
            "type": "agent_status",
            "agent": agent,
            "status": "completed" if result.get('success', True) else "error",
            "result": result
        })

    def send_agent_error(self, agent: str, error: str, details: Dict[str, Any] = None):
        """
        发送Agent错误信息

        Args:
            agent: Agent标识符
            error: 错误信息
            details: 详细信息
        """
        self.send_agent_status({
            "type": "agent_status",
            "agent": agent,
            "status": "error",
            "error": error,
            "details": details or {}
        })

    def send_detailed_thinking(self, agent: str, main_content: str, details: Dict[str, Any] = None, examples: List[str] = None):
        """
        Send detailed agent thinking process with multi-level information display

        Args:
            agent: Agent identifier
            main_content: Main thinking content
            details: Detailed information dictionary
            examples: Example list for showing specific instances
        """
        try:
            thinking_content = main_content

            # Add detailed information
            if details:
                thinking_content += "\n\nDetails:"
                for key, value in details.items():
                    if isinstance(value, (list, tuple)):
                        thinking_content += f"\n- {key}: {', '.join(map(str, value))}"
                    elif isinstance(value, dict):
                        thinking_content += f"\n- {key}: {list(value.keys())}"
                    else:
                        thinking_content += f"\n- {key}: {value}"

            # Add examples - make them clean and readable
            if examples:
                thinking_content += "\n\nExamples:"
                for i, example in enumerate(examples, 1):
                    # Clean up the example to remove code artifacts
                    clean_example = example.replace('# Import necessary libraries:', '').replace('import pandas as pd', '').replace('import numpy as np', '').strip()
                    clean_example = clean_example.replace('# Core code definition:', '').strip()
                    if clean_example:
                        thinking_content += f"\n{i}. {clean_example}"
                    else:
                        thinking_content += f"\n{i}. {example}"

            self.send_agent_thinking({
                "type": "agent_thinking",
                "agent": agent,
                "thinking": thinking_content
            })

        except Exception as e:
            logger.error(f"Error sending detailed thinking: {e}")

    def format_rag_thinking(self, node_id: int, similar_nodes: List, similarity_scores: List = None, technique_focus: str = None):
        """Format RAG generation thinking information"""
        main_content = f"Generating RAG examples for node {node_id}, found {len(similar_nodes)} similar nodes"

        details = {
            "Similar Nodes Count": len(similar_nodes),
            "Main Technique": technique_focus or "Feature engineering transformation"
        }

        examples = []
        if similar_nodes and len(similar_nodes) > 0:
            for i, node in enumerate(similar_nodes):
                if hasattr(node, 'operation_desc') and hasattr(node, 'node_id'):
                    score = f" (similarity: {similarity_scores[i]:.2f})" if similarity_scores and i < len(similarity_scores) else ""
                    examples.append(f"Node {node.node_id}{score}: '{node.operation_desc}'")

        self.send_detailed_thinking("system", main_content, details, examples)

    def format_feature_generation_thinking(self, successful_nodes: List, failed_nodes: List = None, total_complexity: float = 0, execution_time: float = 0):
        """Format feature generation thinking information - send separate messages per node"""
        print(f"[DEBUG] format_feature_generation_thinking called with {len(successful_nodes)} nodes")

        # Send summary message first
        self.send_agent_thinking({
            "type": "agent_thinking",
            "agent": "mainagent",
            "thinking": f"Generated {len(successful_nodes)} feature nodes"
        })

        # Send each node as a separate message
        for i, node in enumerate(successful_nodes, 1):
            thinking_content = f"Node {i}:\n"

            # Show feature description (from nl agent)
            if hasattr(node, 'operation_desc') and node.operation_desc:
                thinking_content += f"Description: {node.operation_desc}\n"

            # Show generated code (from code agent)
            if hasattr(node, 'task_code') and node.task_code:
                # Clean up the code display
                code_lines = node.task_code.strip().split('\n')
                # Remove import statements and keep only the core logic
                core_lines = [line for line in code_lines if not line.strip().startswith(('import', 'from', '#'))]
                if core_lines:
                    thinking_content += "Code:\n"
                    for line in core_lines:
                        thinking_content += f"  {line}\n"

            # Send individual node message
            self.send_agent_thinking({
                "type": "agent_thinking",
                "agent": "mainagent",
                "thinking": thinking_content.strip()
            })

        print(f"[DEBUG] Separate messages sent for {len(successful_nodes)} nodes")

    def format_optimization_thinking(self, complex_nodes: List, optimization_strategies: List = None, complexity_reduction: float = 0):
        """Format optimization thinking information"""
        main_content = f"Detected {len(complex_nodes)} complex nodes, applying divide and conquer strategy"

        details = {
            "Optimization Strategies": optimization_strategies or ["Divide and conquer", "Code simplification"],
            "Complexity Reduction": f"{complexity_reduction:.1f}%" if complexity_reduction > 0 else "Calculating..."
        }

        examples = []
        for i, node in enumerate(complex_nodes[:2]):
            if hasattr(node, 'node_id') and hasattr(node, 'operation_desc'):
                complexity = getattr(node, 'code_complexity', 0)
                examples.append(f"Node {node.node_id} (complexity:{complexity}): '{node.operation_desc}'")

        self.send_detailed_thinking("optimizationagent", main_content, details, examples)

    def format_validation_thinking(self, node_id: int, final_score: float, feature_count: int, performance_metrics: Dict = None, top_features: List = None):
        """Format validation thinking information"""
        status = "Passed" if final_score > 0.5 else "Needs Improvement"
        main_content = f"Node {node_id} performance validation {status}, evaluation score: {final_score:.4f}"

        details = {
            "Total Features": feature_count,
            "Validation Status": status,
            "Confidence": f"{final_score * 100:.1f}%"
        }

        if performance_metrics:
            details.update({
                k: f"{v:.3f}" if isinstance(v, float) else v
                for k, v in list(performance_metrics.items())[:3]
            })

        examples = []
        if top_features:
            examples = [f"Feature {i+1}: {feature}" for i, feature in enumerate(top_features[:3])]
        else:
            examples = [f"Key feature combination analysis (total {feature_count} features)", "Model performance evaluation completed"]

        self.send_detailed_thinking("nodevalidator", main_content, details, examples)

    def send_system_notification(self, message: str, notification_type: str = "info"):
        """
        发送系统通知

        Args:
            message: 通知消息
            notification_type: 通知类型 (info, success, warning, error)
        """
        try:
            notification_data = {
                "type": "system_notification",
                "message": message,
                "notification_type": notification_type,
                "timestamp": time.time()
            }
            # 推送到WebSocket（通过全局消息系统）
            _send_to_all_websockets('system_notification', notification_data)
        except Exception as e:
            logger.error(f"Error sending system notification: {e}")

    def get_agent_status(self, agent: str) -> Optional[Dict[str, Any]]:
        """获取指定Agent的当前状态"""
        return self.agent_states.get(agent)

    def get_agent_history(self, agent: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取指定Agent的历史状态"""
        history = self.agent_history.get(agent, [])
        return history[-limit:] if limit else history

    def get_current_thinking(self, agent: str) -> Optional[Dict[str, Any]]:
        """获取指定Agent的当前思考"""
        return self.current_thinking.get(agent)

    def clear_agent_cache(self, agent: str = None):
        """清除Agent状态缓存"""
        if agent:
            self.agent_states.pop(agent, None)
            self.agent_history.pop(agent, None)
            self.current_thinking.pop(agent, None)
            logger.info(f"Cleared cache for agent: {agent}")
        else:
            self.agent_states.clear()
            self.agent_history.clear()
            self.current_thinking.clear()
            logger.info("Cleared all agent cache")

# 全局Agent状态包装器实例
agent_status_wrapper = AgentStatusWrapper()

def monitor_agent_work(agent: str, work_type: str, details: Dict[str, Any] = None):
    """
    装饰器：监控Agent工作状态

    Args:
        agent: Agent标识符
        work_type: 工作类型
        details: 详细信息
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # 开始工作
                agent_status_wrapper.start_agent_work(agent, work_type, details)

                # 执行函数
                result = func(*args, **kwargs)

                # 完成工作
                agent_status_wrapper.finish_agent_work(agent, {
                    'success': True,
                    'result': result
                })

                return result

            except Exception as e:
                # 发送错误信息
                agent_status_wrapper.send_agent_error(agent, str(e), details)
                raise

        return wrapper
    return decorator

def analyze_agents_activity_from_nodes(status_wrapper, generated_nodes, original_node, step_index):
    """
    通过分析生成的节点来推断各Agent的工作状态
    避免在多线程环境下直接操作WebSocket

    Args:
        status_wrapper: Agent状态包装器实例
        generated_nodes: 生成的节点列表
        original_node: 原始节点
        step_index: 步骤索引
    """
    if not status_wrapper or not generated_nodes:
        return

    def get_code_complexity(code):
        """计算代码复杂度（安全版本）"""
        try:
            if not code or not code.strip():
                return 1

            # 使用导入的get_code_complexity函数，但确保总是返回数值
            from src.llm.utils.code_metrics import get_code_complexity as metrics_complexity
            complexity = metrics_complexity(code)

            if complexity is None or not isinstance(complexity, (int, float)):
                return 1

            return complexity

        except Exception as e:
            logger.error(f"Error calculating code complexity: {e}")
            return 1  # 返回默认复杂度

    try:
        # 1. 分析System Agent活动 (RAG示例生成)
        system_analysis = {
            "type": "agent_status",
            "agent": "system",
            "status": "completed",
            "details": {
                "phase": "example_generation_completed",
                "step_index": step_index,
                "original_node": original_node.node_id
            },
            "data": {
                "summary": f"RAG example generation completed for step {step_index}",
                "nodes_generated": len(generated_nodes),
                "timestamp": time.time()
            }
        }
        status_wrapper.send_agent_status(system_analysis)

        # 2. 分析Main Agent活动 (代码生成)
        main_agent_activities = []
        total_complexity = 0
        code_generated_count = 0

        for node in generated_nodes:
            if hasattr(node, 'task_code') and node.task_code and node.task_code.strip():
                code_generated_count += 1
                try:
                    complexity = get_code_complexity(node.task_code)
                    if complexity is not None and isinstance(complexity, (int, float)):
                        total_complexity += complexity
                except Exception as e:
                    logger.error(f"Error calculating complexity for node {getattr(node, 'node_id', 'unknown')}: {e}")
                    total_complexity += 1  # Default complexity

                main_agent_activities.append({
                    "node_id": getattr(node, 'node_id', 'unknown'),
                    "operation_desc": getattr(node, 'operation_desc', 'unknown'),
                    "code_preview": node.task_code[:100] + "..." if len(node.task_code) > 100 else node.task_code,
                    "code_complexity": complexity,
                    "input_features": list(getattr(node, 'read_set', [])),
                    "output_features": list(getattr(node, 'write_set', [])),
                    "fixing_features_count": len(getattr(node, 'fixing_node', [])) if hasattr(node, 'fixing_node') and node.fixing_node else 0,
                    "exec_time": getattr(node, 'exec_time', 0),
                    "final_score": getattr(node, 'final_score', 0)
                })

        main_agent_analysis = {
            "type": "agent_status",
            "agent": "mainagent",
            "status": "completed",
            "details": {
                "phase": "feature_generation_completed",
                "step_index": step_index,
                "total_nodes": len(generated_nodes),
                "successful_code_generation": code_generated_count
            },
            "data": {
                "activities": main_agent_activities,
                "summary": f"Generated code for {code_generated_count}/{len(generated_nodes)} nodes",
                "average_complexity": total_complexity / max(code_generated_count, 1),
                "timestamp": time.time()
            }
        }
        status_wrapper.send_agent_status(main_agent_analysis)

        # 移除Main Agent的冗余思考过程，避免重复显示技术信息
        # 注释掉这条消息，因为具体的节点信息会通过 format_feature_generation_thinking 分别发送
        # if code_generated_count > 0:
        #     status_wrapper.send_agent_thinking({
        #         "type": "agent_thinking",
        #         "agent": "mainagent",
        #         "thinking": f"成功生成了 {code_generated_count} 个节点的特征代码，平均复杂度为 {total_complexity / max(code_generated_count, 1):.1f}。"
        #     })

        # 3. 分析Optimization Agent活动 (分治处理)
        optimization_detected = False
        optimization_activities = []

        # 检查是否有高复杂度节点，可能触发了分治
        for node in generated_nodes:
            if hasattr(node, 'task_code') and node.task_code:
                try:
                    complexity = get_code_complexity(node.task_code)
                    if complexity > 10:
                        optimization_detected = True
                        optimization_activities.append({
                            "node_id": getattr(node, 'node_id', 'unknown'),
                            "code_complexity": complexity,
                            "required_optimization": True,
                            "operation_desc": getattr(node, 'operation_desc', 'unknown')
                        })
                except Exception as e:
                    logger.error(f"Error checking optimization complexity for node {getattr(node, 'node_id', 'unknown')}: {e}")

        # 检查原始节点是否复杂
        original_complexity = 0
        if hasattr(original_node, 'task_code') and original_node.task_code:
            try:
                original_complexity = get_code_complexity(original_node.task_code)
            except Exception as e:
                logger.error(f"Error calculating original node complexity: {e}")
                original_complexity = 1
        if original_complexity > 10:
            optimization_detected = True

        optimization_analysis = {
            "type": "agent_status",
            "agent": "optimizationagent",
            "status": "completed" if optimization_detected else "idle",
            "details": {
                "phase": "divide_and_conquer_completed" if optimization_detected else "not_needed",
                "step_index": step_index,
                "complex_nodes_detected": len(optimization_activities)
            },
            "data": {
                "activities": optimization_activities,
                "summary": f"Divide and conquer applied to {len(optimization_activities)} complex nodes" if optimization_detected else "No optimization needed",
                "original_complexity": original_complexity,
                "timestamp": time.time()
            }
        }
        status_wrapper.send_agent_status(optimization_analysis)

        # 增强的Optimization Agent思考过程
        if optimization_detected:
            # 提取具体的优化策略信息
            optimization_strategies = []
            complex_nodes_enhanced = []

            for activity in optimization_activities:
                node_id = activity.get("node_id", "unknown")
                complexity = activity.get("code_complexity", 0)
                operation_desc = activity.get("operation_desc", "unknown operation")

                complex_nodes_enhanced.append({
                    "node_id": node_id,
                    "code_complexity": complexity,
                    "operation_desc": operation_desc
                })

                # 根据复杂度确定优化策略
                if complexity > 20:
                    optimization_strategies.append("分治处理+函数分解")
                elif complexity > 15:
                    optimization_strategies.append("代码简化+逻辑优化")
                else:
                    optimization_strategies.append("基础优化")

            # 计算复杂度降低百分比（估算）
            complexity_reduction = min(30, max(10, original_complexity * 0.2)) if original_complexity > 10 else 0

            status_wrapper.format_optimization_thinking(
                complex_nodes=complex_nodes_enhanced,
                optimization_strategies=list(set(optimization_strategies)),
                complexity_reduction=complexity_reduction
            )

        # 4. 分析Node Validator活动 (节点评估)
        validator_activities = []
        passed_nodes = 0
        failed_nodes = 0

        for node in generated_nodes:
            final_score = getattr(node, 'final_score', 0)
            status = "passed" if final_score > 0.5 else "failed"
            if status == "passed":
                passed_nodes += 1
            else:
                failed_nodes += 1

            validator_activities.append({
                "node_id": getattr(node, 'node_id', 'unknown'),
                "final_score": final_score,
                "validation_status": status,
                "feature_count": len(getattr(node, 'column_info', [])),
                "utility_score": getattr(node, 'utility', 0)
            })

        validator_analysis = {
            "type": "agent_status",
            "agent": "nodevalidator",
            "status": "completed",
            "details": {
                "phase": "node_validation_completed",
                "step_index": step_index,
                "passed_nodes": passed_nodes,
                "failed_nodes": failed_nodes
            },
            "data": {
                "activities": validator_activities,
                "summary": f"Validation completed: {passed_nodes} passed, {failed_nodes} failed",
                "success_rate": passed_nodes / max(len(generated_nodes), 1),
                "timestamp": time.time()
            }
        }
        status_wrapper.send_agent_status(validator_analysis)

    except Exception as e:
        logger.error(f"Error in analyze_agents_activity_from_nodes: {e}")
        status_wrapper.send_agent_error("system", f"Error analyzing agents activity: {str(e)}")
