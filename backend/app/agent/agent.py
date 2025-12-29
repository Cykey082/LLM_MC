import asyncio
import re
from typing import Optional, Dict, Any

from app.bot.client import bot_client
from app.llm.client import llm_client
from app.llm.prompts import get_agent_system_prompt, format_observation
from app.script.executor import script_executor, BotAPI
from app.skills.manager import skill_manager
from app.config import settings


class Agent:
    """
    Main Agent class
    Coordinates perception, decision-making, and action execution
    """
    
    def __init__(self):
        self.is_running = False
        self.last_action: Optional[Dict[str, Any]] = None
        self.last_action_result: Optional[Dict[str, Any]] = None
        self._tick_task: Optional[asyncio.Task] = None
        self._pending_chat: list = []
        
        # 技能测试相关
        self._current_test_task: Optional[asyncio.Task] = None
        self._current_test_name: Optional[str] = None
        self._test_cancelled: bool = False
        self._skill_testing: bool = False  # 是否正在测试技能（暂停LLM）
    
    async def start(self):
        """Start the agent's decision loop"""
        if self.is_running:
            print("[Agent] Already running")
            return
        
        print("[Agent] Starting agent loop...")
        self.is_running = True
        
        # Register event handler for chat messages
        bot_client.add_event_handler(self._handle_bot_event)
        
        # Start tick loop
        self._tick_task = asyncio.create_task(self._tick_loop())
    
    async def stop(self):
        """Stop the agent's decision loop"""
        if not self.is_running:
            return
        
        print("[Agent] Stopping agent loop...")
        self.is_running = False
        
        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
        
        bot_client.remove_event_handler(self._handle_bot_event)
    
    async def _tick_loop(self):
        """Main decision loop"""
        error_count = 0
        while self.is_running:
            try:
                await self.tick()
                error_count = 0  # 重置错误计数
            except Exception as e:
                error_count += 1
                if error_count <= 3:  # 只打印前3次错误
                    print(f"[Agent] 错误: {e}")
                elif error_count == 4:
                    print("[Agent] 后续相同错误将不再显示...")
            
            await asyncio.sleep(settings.agent_tick_rate)
    
    async def tick(self):
        """Single decision-action cycle"""
        if not self.is_running:
            return
        
        # 如果正在测试技能，跳过LLM决策
        if self._skill_testing:
            return
        
        # 先检查Bot是否已连接
        try:
            status = await bot_client.get_status()
            if not status.get("connected"):
                return  # Bot未连接，静默跳过
        except Exception:
            return  # 无法获取状态，静默跳过
        
        try:
            # 1. Get observation from bot
            observation = await bot_client.get_observation()
            
            # Add any pending chat messages
            if self._pending_chat:
                if "chatMessages" not in observation:
                    observation["chatMessages"] = []
                observation["chatMessages"].extend(self._pending_chat)
                self._pending_chat = []
            
            # Check if there's anything interesting to respond to
            has_chat = bool(observation.get("chatMessages"))
            has_events = bool(observation.get("events"))
            
            # Skip if nothing interesting and we just waited
            if (not has_chat and not has_events and 
                self.last_action and self.last_action.get("action") == "wait"):
                return
            
            # 2. Format observation for LLM
            user_message = format_observation(observation)
            
            if self.last_action_result:
                user_message += f"\nLast action result: {self.last_action_result}"
            
            # 3. Get decision from LLM
            print("[Agent] Thinking...")
            
            system_prompt = get_agent_system_prompt({
                "position": observation.get("position"),
                "health": observation.get("health"),
                "time": observation.get("time")
            })
            
            response = await llm_client.chat_json(system_prompt, user_message)
            
            if settings.debug:
                print(f"[Agent] LLM Response: {response}")
            
            # 4. Execute action
            if response and response.get("action"):
                print(f"[Agent] Thought: {response.get('thought', 'N/A')}")
                print(f"[Agent] Action: {response['action']} {response.get('parameters', {})}")
                
                self.last_action = response
                
                # 特殊处理脚本执行动作
                if response["action"] == "executeScript":
                    self.last_action_result = await self._execute_script(
                        response.get("parameters", {})
                    )
                else:
                    self.last_action_result = await bot_client.execute_action(
                        response["action"],
                        response.get("parameters", {})
                    )
                
                print(f"[Agent] Result: {self.last_action_result.get('message', 'N/A')}")
            else:
                print("[Agent] No valid action in response")
                
        except Exception as e:
            print(f"[Agent] Error: {e}")
            self.last_action_result = {"success": False, "message": str(e)}
    
    async def force_tick(self):
        """Force an immediate decision cycle"""
        await self.tick()
    
    async def _execute_script(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Python script for complex actions"""
        script = params.get("script", "")
        description = params.get("description", "Unnamed script")
        timeout = params.get("timeout", 300)  # 默认5分钟
        
        if not script:
            return {"success": False, "message": "No script provided"}
        
        print(f"[Agent] Executing script: {description}")
        
        try:
            result = await script_executor.execute(
                script=script,
                timeout=timeout
            )
            
            if result["success"]:
                # 构建有意义的结果摘要
                actions = result.get("actions", [])
                action_count = len(actions)
                script_result = result.get('result')
                
                # 构建动作摘要
                if actions:
                    # 获取每个动作的结果摘要
                    action_summaries = []
                    for action_info in actions[-5:]:  # 最多显示最后5个动作
                        action_name = action_info.get("action", "unknown")
                        action_result = action_info.get("result", {})
                        success = action_result.get("success", False)
                        msg = action_result.get("message", "")
                        status = "✓" if success else "✗"
                        action_summaries.append(f"{status}{action_name}: {msg[:50]}")
                    
                    actions_text = "; ".join(action_summaries)
                    if action_count > 5:
                        actions_text = f"...and {action_count - 5} more; " + actions_text
                else:
                    actions_text = "No actions executed"
                
                # 如果脚本有返回值，使用返回值；否则使用动作摘要
                if script_result is not None:
                    message = f"Script result: {script_result}"
                else:
                    message = f"Executed {action_count} actions: {actions_text}"
                
                return {
                    "success": True,
                    "message": message,
                    "logs": result.get("logs", []),
                    "actions": actions,
                    "action_count": action_count,
                    "execution_time": result.get("execution_time", 0)
                }
            else:
                error_msg = result.get('error', 'Unknown error')
                # 如果有traceback，打印到控制台方便调试
                if result.get('traceback'):
                    print(f"[Agent] Script traceback:\n{result['traceback']}")
                return {
                    "success": False,
                    "message": f"Script failed: {error_msg}",
                    "logs": result.get("logs", []),
                    "actions": result.get("actions", [])
                }
        except Exception as e:
            import traceback
            print(f"[Agent] Script execution error:\n{traceback.format_exc()}")
            return {"success": False, "message": f"Script execution error: {str(e)}"}
    
    async def _handle_bot_event(self, event: Dict[str, Any]):
        """Handle events from the bot WebSocket"""
        event_type = event.get("type")
        
        if event_type == "chat":
            message = event.get("message", "")
            username = event.get("username", "")
            
            # 检查是否是测试指令
            if message.startswith("%test "):
                # 异步执行测试，不阻塞事件处理
                asyncio.create_task(self._handle_test_command(message, username))
                return
            
            # 检查是否是停止指令
            if message.strip() == "%stop":
                asyncio.create_task(self._handle_stop_command(username))
                return
            
            # 检查是否是列出技能指令
            if message.strip() == "%skills":
                asyncio.create_task(self._handle_skills_command(username))
                return
            
            # 检查是否是帮助指令
            if message.strip() == "%help":
                asyncio.create_task(self._handle_help_command(username))
                return
            
            # Store chat message for next tick
            self._pending_chat.append({
                "username": username,
                "message": message
            })
    
    async def _handle_test_command(self, message: str, username: str):
        """
        处理 %test 指令，直接测试技能
        
        格式: %test 技能名
        或者: %test 技能名(参数1=值1, 参数2=值2)
        """
        # 检查是否有正在运行的测试
        if self._current_test_task and not self._current_test_task.done():
            await bot_client.execute_action("chat", {
                "message": f"@{username} 已有技能'{self._current_test_name}'在运行喵~ 用 %stop 可以停止"
            })
            return
        
        try:
            # 解析指令
            command = message[6:].strip()  # 去掉 "%test "
            
            # 解析技能名和参数
            match = re.match(r'^([^(]+)(?:\(([^)]*)\))?$', command)
            if not match:
                await bot_client.execute_action("chat", {
                    "message": f"@{username} 格式错误喵~ 用法: %test 技能名 或 %test 技能名(参数=值)"
                })
                return
            
            skill_name = match.group(1).strip()
            params_str = match.group(2)
            
            # 解析参数
            kwargs = {}
            if params_str:
                # 解析 key=value 格式的参数
                param_pairs = params_str.split(',')
                for pair in param_pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # 尝试解析值类型
                        try:
                            # 尝试解析为数字
                            if '.' in value:
                                kwargs[key] = float(value)
                            else:
                                kwargs[key] = int(value)
                        except ValueError:
                            # 去掉引号
                            if (value.startswith('"') and value.endswith('"')) or \
                               (value.startswith("'") and value.endswith("'")):
                                value = value[1:-1]
                            kwargs[key] = value
            
            # 检查技能是否存在
            skill = skill_manager.get_skill(skill_name)
            if not skill:
                skills = skill_manager.list_skills()
                skill_names = [s['name'] for s in skills]
                await bot_client.execute_action("chat", {
                    "message": f"@{username} 技能'{skill_name}'不存在喵~ 可用技能: {', '.join(skill_names) or '无'}"
                })
                return
            
            # 重置取消标志
            self._test_cancelled = False
            self._current_test_name = skill_name
            self._skill_testing = True  # 暂停LLM决策
            
            # 通知开始测试
            await bot_client.execute_action("chat", {
                "message": f"@{username} 开始测试技能'{skill_name}'喵~ (用 %stop 可停止，LLM已暂停)"
            })
            
            print(f"[Agent] 测试技能: {skill_name}, 参数: {kwargs} (LLM已暂停)")
            
            # 创建测试任务
            self._current_test_task = asyncio.create_task(
                self._run_skill_test(skill_name, kwargs, username)
            )
            
        except Exception as e:
            import traceback
            print(f"[Agent] 技能测试错误: {traceback.format_exc()}")
            await bot_client.execute_action("chat", {
                "message": f"@{username} 测试出错喵: {str(e)[:50]}"
            })
            self._current_test_task = None
            self._current_test_name = None
    
    async def _run_skill_test(self, skill_name: str, kwargs: dict, username: str):
        """运行技能测试（带超时和取消支持）"""
        try:
            # 创建 BotAPI 并执行技能
            bot_api = BotAPI()
            
            # 使用 wait_for 添加超时（默认5分钟）
            try:
                result = await asyncio.wait_for(
                    bot_api.useSkill(skill_name, **kwargs),
                    timeout=300.0  # 5分钟超时
                )
            except asyncio.TimeoutError:
                await bot_client.execute_action("chat", {
                    "message": f"@{username} 技能'{skill_name}'执行超时(5分钟)喵~"
                })
                # 停止移动
                await bot_client.execute_action("stopMoving", {})
                return
            except asyncio.CancelledError:
                await bot_client.execute_action("chat", {
                    "message": f"@{username} 技能'{skill_name}'已被停止喵~"
                })
                # 停止移动
                await bot_client.execute_action("stopMoving", {})
                return
            
            # 检查是否被取消
            if self._test_cancelled:
                return
            
            # 报告结果
            if isinstance(result, dict):
                success = result.get("success", True)
                msg = result.get("message", str(result))
                status = "成功" if success else "失败"
            else:
                status = "完成"
                msg = str(result) if result else "无返回值"
            
            await bot_client.execute_action("chat", {
                "message": f"@{username} 技能测试{status}: {msg[:100]}"
            })
            
            print(f"[Agent] 技能测试结果: {result}")
            
        except asyncio.CancelledError:
            # 被 %stop 取消
            print(f"[Agent] 技能测试被取消: {skill_name}")
            await bot_client.execute_action("stopMoving", {})
        except Exception as e:
            import traceback
            print(f"[Agent] 技能测试错误: {traceback.format_exc()}")
            await bot_client.execute_action("chat", {
                "message": f"@{username} 测试出错喵: {str(e)[:50]}"
            })
        finally:
            self._current_test_task = None
            self._current_test_name = None
            self._skill_testing = False  # 恢复LLM决策
            print(f"[Agent] 技能测试结束，LLM已恢复")
    
    async def _handle_stop_command(self, username: str):
        """处理 %stop 指令，停止当前技能测试"""
        if not self._current_test_task or self._current_test_task.done():
            await bot_client.execute_action("chat", {
                "message": f"@{username} 没有正在运行的技能喵~"
            })
            return
        
        skill_name = self._current_test_name or "未知技能"
        self._test_cancelled = True
        self._skill_testing = False  # 恢复LLM决策
        
        # 取消任务
        self._current_test_task.cancel()
        
        # 停止bot移动
        try:
            await bot_client.execute_action("stopMoving", {})
        except:
            pass
        
        print(f"[Agent] 停止技能测试: {skill_name}，LLM已恢复")
        await bot_client.execute_action("chat", {
            "message": f"@{username} 已停止技能'{skill_name}'喵~ LLM已恢复"
        })
    
    async def _handle_help_command(self, username: str):
        """处理 %help 指令，显示帮助信息"""
        help_text = (
            "可用指令: "
            "%skills - 列出技能 | "
            "%test 技能名 - 测试技能 | "
            "%test 技能名(参数=值) - 带参数测试 | "
            "%stop - 停止当前技能"
        )
        await bot_client.execute_action("chat", {
            "message": f"@{username} {help_text}"
        })
    
    async def _handle_skills_command(self, username: str):
        """处理 %skills 指令，列出所有技能"""
        try:
            skills = skill_manager.list_skills()
            
            if not skills:
                await bot_client.execute_action("chat", {
                    "message": f"@{username} 还没有保存任何技能喵~"
                })
                return
            
            # 格式化技能列表
            skill_list = []
            for s in skills:
                params = s.get('params', [])
                param_str = f"({', '.join(params)})" if params else ""
                skill_list.append(f"{s['name']}{param_str}")
            
            await bot_client.execute_action("chat", {
                "message": f"@{username} 可用技能: {', '.join(skill_list)}"
            })
            
        except Exception as e:
            await bot_client.execute_action("chat", {
                "message": f"@{username} 获取技能列表失败喵: {str(e)[:30]}"
            })
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            "is_running": self.is_running,
            "last_action": self.last_action,
            "last_action_result": self.last_action_result,
            "pending_chat_count": len(self._pending_chat),
            "skill_testing": self._skill_testing,
            "current_test_skill": self._current_test_name
        }


# Singleton instance
agent = Agent()