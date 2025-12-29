"""
技能: 打怪
描述: 自动寻找并击杀敌对生物，支持指定类型和数量
"""

async def 打怪(bot, count=1, mob_type=None):
    """
    自动寻找并击杀敌对生物
    
    策略：
    1. 扫描附近的敌对生物
    2. 自动装备最好的武器
    3. 走近目标并持续攻击
    4. 目标死亡后寻找下一个
    
    Args:
        bot: BotAPI实例
        count: 要击杀的数量，默认1个
        mob_type: 指定怪物类型（可选），如 "zombie", "skeleton" 等
                  如果不指定，会攻击任意敌对生物
    """
    
    # 敌对生物列表（按危险程度排序）
    hostile_mobs = [
        "creeper",      # 苦力怕（最危险，会爆炸）
        "skeleton",     # 骷髅（远程攻击）
        "witch",        # 女巫（远程魔法）
        "phantom",      # 幻翼
        "blaze",        # 烈焰人
        "ghast",        # 恶魂
        "zombie",       # 僵尸
        "drowned",      # 溺尸
        "husk",         # 尸壳
        "spider",       # 蜘蛛
        "cave_spider",  # 洞穴蜘蛛
        "enderman",     # 末影人
        "slime",        # 史莱姆
        "magma_cube",   # 岩浆怪
        "pillager",     # 掠夺者
        "vindicator",   # 卫道士
        "ravager",      # 劫掠兽
        "evoker",       # 唤魔者
        "vex",          # 恼鬼
        "zombified_piglin",  # 僵尸猪灵
        "piglin_brute",      # 猪灵蛮兵
        "warden",       # 监守者（极其危险）
    ]
    
    # 武器优先级列表（从好到差）
    weapon_priority = [
        "netherite_sword",
        "diamond_sword",
        "iron_sword",
        "golden_sword",
        "stone_sword",
        "wooden_sword",
        "netherite_axe",
        "diamond_axe",
        "iron_axe",
        "stone_axe",
        "wooden_axe",
    ]
    
    # 内嵌辅助函数：装备最好的武器
    async def equip_best_weapon():
        """装备最好的武器"""
        inventory = await bot.viewInventory()
        items = inventory.get("inventory", [])
        
        if not items:
            return None
        
        # 查找优先级最高的武器
        for weapon in weapon_priority:
            for item in items:
                if weapon in item.get("name", ""):
                    result = await bot.equipItem(item["name"])
                    if result.get("success"):
                        return item["name"]
        
        return None
    
    # 内嵌辅助函数：寻找附近的敌对生物
    async def find_hostile_mob(specific_type=None):
        """
        寻找附近的敌对生物
        
        Returns:
            目标信息 {"name": str, "position": dict, "distance": float} 或 None
        """
        # 扫描附近实体
        scan_result = await bot.scanEntities(range=24)
        
        if not scan_result.get("success"):
            return None
        
        entities = scan_result.get("entities", [])
        
        # 过滤出敌对生物
        hostile_entities = []
        for entity in entities:
            entity_name = entity.get("name", "")
            
            # 如果指定了类型，只查找该类型
            if specific_type:
                if entity_name == specific_type:
                    hostile_entities.append(entity)
            # 否则查找所有敌对生物
            elif entity_name in hostile_mobs or entity.get("isHostile", False):
                hostile_entities.append(entity)
        
        if not hostile_entities:
            return None
        
        # 按距离排序，选择最近的
        hostile_entities.sort(key=lambda e: e.get("distance", 999))
        target = hostile_entities[0]
        
        return {
            "name": target.get("name", "unknown"),
            "position": {
                "x": target.get("x", 0),
                "y": target.get("y", 0),
                "z": target.get("z", 0)
            },
            "distance": target.get("distance", 0)
        }
    
    # 内嵌辅助函数：追踪并击杀目标
    async def chase_and_kill(mob_name, initial_pos):
        """
        追踪并击杀目标
        
        策略：
        1. 如果距离较远，先走近
        2. 持续攻击直到目标消失
        3. 定期检查目标是否还存在
        """
        
        max_attack_attempts = 30  # 最多攻击30次
        attack_interval = 0.5     # 攻击间隔（秒）
        attack_count = 0
        last_known_pos = initial_pos
        
        for attempt in range(max_attack_attempts):
            # 重新扫描，确认目标还存在
            scan_result = await bot.scanEntities(range=24)
            entities = scan_result.get("entities", [])
            
            # 查找目标（同类型，距离最近）
            target = None
            for entity in entities:
                if entity.get("name") == mob_name:
                    target = entity
                    break
            
            if not target:
                # 目标可能已死亡或逃出范围
                if attack_count >= 3:
                    # 攻击了几次后目标消失，很可能是打死了
                    return {"success": True, "message": "Target eliminated"}
                else:
                    return {"success": False, "message": "Target not found"}
            
            # 更新目标位置
            target_x = target.get("x", 0)
            target_y = target.get("y", 0)
            target_z = target.get("z", 0)
            target_distance = target.get("distance", 999)
            last_known_pos = {"x": target_x, "y": target_y, "z": target_z}
            
            # 如果太远，先走近
            if target_distance > 4:
                bot.log(f"目标距离 {target_distance:.1f}，正在接近...")
                # 走到目标附近（留一点距离）
                await bot.goTo(target_x, target_y, target_z)
                # goTo 可能会走到很近，但我们继续循环攻击
            
            # 看向目标
            await bot.lookAt(target_x, target_y + 1, target_z)  # 看向稍高一点的位置
            
            # 攻击！
            attack_result = await bot.attack(mob_name)
            
            if attack_result.get("success"):
                attack_count += 1
                bot.log(f"攻击 {mob_name} 第 {attack_count} 次")
            else:
                # 攻击失败，可能距离太远
                bot.log(f"攻击失败: {attack_result.get('message', '')}")
            
            # 等待攻击冷却
            await bot.wait(attack_interval)
            
            # 检查自身生命值
            health_info = await bot.getHealth()
            if health_info.get("health", 20) <= 4:
                bot.log("生命值危险，撤退！")
                await bot.stopMoving()
                return {"success": False, "message": "Health critical, retreating"}
        
        # 超过最大攻击次数
        return {"success": False, "message": f"Max attacks ({max_attack_attempts}) reached"}
    
    # ===== 主逻辑开始 =====
    
    killed = 0
    failed_attempts = 0
    max_failed = 5  # 连续失败5次就放弃
    
    bot.log(f"开始打怪，目标: {count} 个" + (f" ({mob_type})" if mob_type else " (任意敌对生物)"))
    
    # 尝试装备武器
    equipped_weapon = await equip_best_weapon()
    if equipped_weapon:
        bot.log(f"已装备武器: {equipped_weapon}")
        await bot.chat(f"拿起了{equipped_weapon}准备战斗喵~")
    else:
        bot.log("没有找到武器，将使用空手战斗")
        await bot.chat("没有武器...只能用拳头了喵...")
    
    while killed < count and failed_attempts < max_failed:
        # 检查生命值
        health_info = await bot.getHealth()
        current_health = health_info.get("health", 20)
        
        if current_health <= 6:  # 生命值低于3心
            bot.log(f"生命值过低 ({current_health})，暂停战斗")
            await bot.chat(f"血量太低了喵！({current_health}/20) 先跑为敬~")
            return {
                "success": killed > 0,
                "killed": killed,
                "target": count,
                "message": f"生命值过低，已击杀 {killed}/{count}"
            }
        
        # 扫描敌对生物
        target = await find_hostile_mob(mob_type)
        
        if not target:
            bot.log("附近没有找到敌对生物")
            # 尝试等待一会儿看看有没有刷新
            if failed_attempts < 2:
                await bot.chat("找不到怪物，等一下看看喵~")
                await bot.wait(3)
                failed_attempts += 1
                continue
            else:
                await bot.chat(f"附近没有怪物了喵~ 已击杀 {killed}/{count}")
                return {
                    "success": killed > 0,
                    "killed": killed,
                    "target": count,
                    "message": f"附近没有敌对生物，已击杀 {killed}/{count}"
                }
        
        mob_name = target["name"]
        mob_pos = target["position"]
        mob_distance = target["distance"]
        
        bot.log(f"发现目标: {mob_name} 在 ({mob_pos['x']}, {mob_pos['y']}, {mob_pos['z']}), 距离: {mob_distance:.1f}")
        await bot.chat(f"发现{mob_name}！冲啊喵~")
        
        # 追踪并攻击目标
        kill_result = await chase_and_kill(mob_name, mob_pos)
        
        if kill_result["success"]:
            killed += 1
            failed_attempts = 0
            bot.log(f"击杀成功! 进度: {killed}/{count}")
            await bot.chat(f"打倒了{mob_name}喵~ ({killed}/{count})")
        else:
            bot.log(f"攻击失败: {kill_result.get('message', '未知原因')}")
            failed_attempts += 1
            
            # 如果是因为找不到目标了（可能已经死了或跑了）
            if "not found" in kill_result.get("message", "").lower():
                # 可能我们打死了但没检测到
                killed += 0.5  # 半个计数，给予一定的宽容
                if killed >= count:
                    break
    
    # 战斗结束
    await bot.stopMoving()
    
    final_killed = int(killed)
    if final_killed >= count:
        await bot.chat(f"战斗胜利喵！共击杀 {final_killed} 个敌人!")
        return {
            "success": True,
            "killed": final_killed,
            "target": count,
            "message": f"成功击杀 {final_killed} 个敌对生物"
        }
    else:
        await bot.chat(f"战斗结束喵... 击杀了 {final_killed}/{count} 个")
        return {
            "success": False,
            "killed": final_killed,
            "target": count,
            "message": f"战斗中断，击杀了 {final_killed}/{count}"
        }