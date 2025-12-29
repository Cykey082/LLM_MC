"""
技能: 挖矿
描述: 自动寻找并采集指定类型的矿石
"""

async def 挖矿(bot, oreType="iron_ore", count=5):
    """
    自动寻找并采集指定矿石
    
    Args:
        bot: BotAPI实例
        oreType: 矿石类型（默认iron_ore），支持:
                 - coal_ore (煤矿)
                 - iron_ore (铁矿)
                 - copper_ore (铜矿)
                 - gold_ore (金矿)
                 - diamond_ore (钻石矿)
                 - emerald_ore (绿宝石矿)
                 - lapis_ore (青金石矿)
                 - redstone_ore (红石矿)
        count: 要采集的数量（默认5）
    
    Returns:
        采集结果
    """
    
    # 内嵌辅助函数：装备最好的镐子
    async def equip_best_pickaxe():
        """装备最好的镐子"""
        pickaxe_priority = [
            "netherite_pickaxe",
            "diamond_pickaxe",
            "iron_pickaxe",
            "golden_pickaxe",
            "stone_pickaxe",
            "wooden_pickaxe",
        ]
        
        inventory = await bot.viewInventory()
        items = inventory.get("inventory", [])
        
        for pickaxe in pickaxe_priority:
            for item in items:
                if item.get("name") == pickaxe:
                    result = await bot.equipItem(pickaxe)
                    if result.get("success"):
                        bot.log(f"装备了 {pickaxe}")
                        return pickaxe
        
        bot.log("没有找到镐子，使用空手")
        return None
    
    # 矿石对应的深层矿石名称
    ore_variants = {
        "coal_ore": ["coal_ore", "deepslate_coal_ore"],
        "iron_ore": ["iron_ore", "deepslate_iron_ore"],
        "copper_ore": ["copper_ore", "deepslate_copper_ore"],
        "gold_ore": ["gold_ore", "deepslate_gold_ore"],
        "diamond_ore": ["diamond_ore", "deepslate_diamond_ore"],
        "emerald_ore": ["emerald_ore", "deepslate_emerald_ore"],
        "lapis_ore": ["lapis_ore", "deepslate_lapis_ore"],
        "redstone_ore": ["redstone_ore", "deepslate_redstone_ore"],
    }
    
    # 获取所有可能的矿石名称
    if oreType in ore_variants:
        target_ores = ore_variants[oreType]
    else:
        target_ores = [oreType]
    
    bot.log(f"开始挖矿: {oreType}，目标: {count} 个")
    await bot.chat(f"开始挖 {oreType} 喵~ 目标 {count} 个")
    
    # 先装备镐子
    await equip_best_pickaxe()
    
    mined = 0
    failed_attempts = 0
    max_failed = 10  # 连续失败次数
    tried_positions = set()
    
    while mined < count and failed_attempts < max_failed:
        # 检查生命值和饥饿值
        health = await bot.getHealth()
        if health.get("health", 20) <= 6:
            await bot.chat("血量太低了，先回去喵...")
            return {
                "success": mined > 0,
                "mined": mined,
                "target": count,
                "message": f"因生命值过低停止，已采集 {mined}/{count}"
            }
        
        if health.get("food", 20) <= 6:
            bot.log("饥饿值低，尝试吃东西")
            await bot.eat()
        
        # 每次循环都检查并装备最佳镐子
        await equip_best_pickaxe()
        
        # 寻找最近的矿石
        best_ore = None
        best_distance = float('inf')
        
        for ore_name in target_ores:
            result = await bot.findBlock(ore_name, 32)
            if result.get("found"):
                pos = result.get("position", {})
                pos_key = f"{pos.get('x')},{pos.get('y')},{pos.get('z')}"
                
                if pos_key in tried_positions:
                    continue
                
                distance = result.get("distance", 999)
                if distance < best_distance:
                    best_distance = distance
                    best_ore = {
                        "name": ore_name,
                        "position": pos,
                        "distance": distance
                    }
        
        if not best_ore:
            bot.log("附近没有找到矿石")
            failed_attempts += 1
            
            if failed_attempts >= 3:
                await bot.chat(f"找不到 {oreType} 了喵~ 已采集 {mined}/{count}")
                return {
                    "success": mined > 0,
                    "mined": mined,
                    "target": count,
                    "message": f"附近没有矿石了，已采集 {mined}/{count}"
                }
            
            # 等待一下再找
            await bot.wait(2)
            continue
        
        pos = best_ore["position"]
        ore_name = best_ore["name"]
        pos_key = f"{pos.get('x')},{pos.get('y')},{pos.get('z')}"
        
        bot.log(f"找到 {ore_name} 在 ({pos.get('x')}, {pos.get('y')}, {pos.get('z')}), 距离: {best_ore['distance']:.1f}")
        
        # 采集矿石
        collect_result = await bot.collectBlock(ore_name)
        
        if collect_result.get("success"):
            mined += 1
            failed_attempts = 0
            bot.log(f"采集成功! 进度: {mined}/{count}")
            
            if mined < count:
                await bot.chat(f"挖到第 {mined} 个啦喵~ ({mined}/{count})")
        else:
            error_msg = collect_result.get("message", "未知错误")
            bot.log(f"采集失败: {error_msg}")
            tried_positions.add(pos_key)
            failed_attempts += 1
    
    # 完成
    if mined >= count:
        await bot.chat(f"挖矿完成喵~ 共挖了 {mined} 个 {oreType}!")
        return {
            "success": True,
            "mined": mined,
            "target": count,
            "oreType": oreType,
            "message": f"成功采集 {mined} 个 {oreType}"
        }
    else:
        await bot.chat(f"挖矿中断喵... 只挖到 {mined}/{count} 个")
        return {
            "success": False,
            "mined": mined,
            "target": count,
            "oreType": oreType,
            "message": f"采集中断，只采集了 {mined}/{count} 个"
        }