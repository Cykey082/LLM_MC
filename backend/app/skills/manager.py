"""
Skill Manager - 管理可复用的技能代码

技能结构:
{
    "name": "技能名称",
    "description": "技能描述",
    "params": ["参数1", "参数2"],  # 可选参数列表
    "code": "技能代码"
}
"""

import os
import json
import re
from typing import Dict, List, Optional
from pathlib import Path


class SkillManager:
    """技能管理器 - 保存、加载、执行技能"""
    
    def __init__(self, skills_dir: str = None):
        """
        初始化技能管理器
        
        Args:
            skills_dir: 技能存储目录，默认为 backend/skills
        """
        if skills_dir is None:
            # 默认技能目录
            base_dir = Path(__file__).parent.parent.parent
            skills_dir = base_dir / "skills"
        
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        # 技能索引文件
        self.index_file = self.skills_dir / "index.json"
        
        # 内存中的技能索引
        self._index: Dict[str, dict] = {}
        
        # 加载索引
        self._load_index()
    
    def _load_index(self):
        """从文件加载技能索引"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self._index = json.load(f)
            except Exception as e:
                print(f"[SkillManager] 加载索引失败: {e}")
                self._index = {}
        else:
            self._index = {}
    
    def _save_index(self):
        """保存技能索引到文件"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SkillManager] 保存索引失败: {e}")
    
    def _skill_file(self, name: str) -> Path:
        """获取技能代码文件路径"""
        # 将技能名转为安全的文件名
        safe_name = re.sub(r'[^\w\-]', '_', name)
        return self.skills_dir / f"{safe_name}.py"
    
    def save_skill(self, name: str, description: str, code: str, 
                   params: List[str] = None) -> dict:
        """
        保存技能
        
        Args:
            name: 技能名称
            description: 技能描述
            code: 技能代码（Python函数体）
            params: 参数列表
            
        Returns:
            保存结果
        """
        params = params or []
        
        # 验证技能名
        if not name or not name.strip():
            return {"success": False, "error": "技能名不能为空"}
        
        name = name.strip()
        
        # 生成完整的函数代码
        param_str = ", ".join(params) if params else ""
        full_code = self._wrap_skill_code(name, description, code, param_str)
        
        # 保存代码文件
        skill_file = self._skill_file(name)
        try:
            with open(skill_file, 'w', encoding='utf-8') as f:
                f.write(full_code)
        except Exception as e:
            return {"success": False, "error": f"保存代码失败: {e}"}
        
        # 更新索引
        self._index[name] = {
            "name": name,
            "description": description,
            "params": params,
            "file": skill_file.name
        }
        self._save_index()
        
        return {
            "success": True, 
            "message": f"技能 '{name}' 已保存",
            "skill": self._index[name]
        }
    
    def _wrap_skill_code(self, name: str, description: str, 
                         code: str, param_str: str) -> str:
        """将技能代码包装成完整的函数"""
        # 处理代码缩进
        lines = code.split('\n')
        indented_lines = ['    ' + line if line.strip() else line for line in lines]
        indented_code = '\n'.join(indented_lines)
        
        return f'''"""
技能: {name}
描述: {description}
"""

async def {self._safe_func_name(name)}(bot{", " + param_str if param_str else ""}):
    """
    {description}
    
    Args:
        bot: BotAPI实例
{self._format_param_docs(param_str)}
    """
{indented_code}
'''
    
    def _safe_func_name(self, name: str) -> str:
        """将技能名转为安全的函数名"""
        # 替换非法字符为下划线
        safe = re.sub(r'[^\w]', '_', name)
        # 确保不以数字开头
        if safe and safe[0].isdigit():
            safe = '_' + safe
        return safe or 'unnamed_skill'
    
    def _format_param_docs(self, param_str: str) -> str:
        """格式化参数文档"""
        if not param_str:
            return ""
        params = [p.strip() for p in param_str.split(',')]
        docs = []
        for p in params:
            docs.append(f"        {p}: 参数")
        return '\n'.join(docs)
    
    def get_skill(self, name: str) -> Optional[dict]:
        """
        获取技能信息
        
        Args:
            name: 技能名称
            
        Returns:
            技能信息字典，包含代码
        """
        if name not in self._index:
            return None
        
        skill_info = self._index[name].copy()
        
        # 读取代码
        skill_file = self._skill_file(name)
        if skill_file.exists():
            try:
                with open(skill_file, 'r', encoding='utf-8') as f:
                    skill_info['full_code'] = f.read()
            except Exception as e:
                skill_info['full_code'] = f"# 读取失败: {e}"
        
        return skill_info
    
    def get_skill_code(self, name: str) -> Optional[str]:
        """
        获取可直接执行的技能代码
        
        Args:
            name: 技能名称
            
        Returns:
            技能代码字符串
        """
        skill = self.get_skill(name)
        if not skill:
            return None
        return skill.get('full_code')
    
    def list_skills(self) -> List[dict]:
        """
        列出所有技能
        
        Returns:
            技能列表（不含代码）
        """
        return list(self._index.values())
    
    def delete_skill(self, name: str) -> dict:
        """
        删除技能
        
        Args:
            name: 技能名称
            
        Returns:
            删除结果
        """
        if name not in self._index:
            return {"success": False, "error": f"技能 '{name}' 不存在"}
        
        # 删除代码文件
        skill_file = self._skill_file(name)
        try:
            if skill_file.exists():
                skill_file.unlink()
        except Exception as e:
            return {"success": False, "error": f"删除文件失败: {e}"}
        
        # 从索引中移除
        del self._index[name]
        self._save_index()
        
        return {"success": True, "message": f"技能 '{name}' 已删除"}
    
    def generate_skill_call(self, name: str, args: Dict[str, any] = None) -> str:
        """
        生成调用技能的代码
        
        Args:
            name: 技能名称
            args: 参数字典
            
        Returns:
            调用代码字符串
        """
        if name not in self._index:
            return f"# 错误: 技能 '{name}' 不存在"
        
        skill = self._index[name]
        func_name = self._safe_func_name(name)
        
        # 生成参数字符串
        args = args or {}
        param_strs = []
        for param in skill.get('params', []):
            if param in args:
                value = args[param]
                if isinstance(value, str):
                    param_strs.append(f'{param}="{value}"')
                else:
                    param_strs.append(f'{param}={value}')
            else:
                param_strs.append(f'{param}=None')
        
        params_code = ", ".join(param_strs)
        
        return f"await {func_name}(bot{', ' + params_code if params_code else ''})"
    
    def get_skills_description(self) -> str:
        """
        获取所有技能的描述文本（用于LLM提示词）
        
        Returns:
            技能描述文本
        """
        if not self._index:
            return "当前没有保存的技能。"
        
        lines = ["已保存的技能:"]
        for name, skill in self._index.items():
            params = skill.get('params', [])
            param_str = f"({', '.join(params)})" if params else "()"
            lines.append(f"  - {name}{param_str}: {skill.get('description', '无描述')}")
        
        return '\n'.join(lines)


# 全局技能管理器实例
skill_manager = SkillManager()