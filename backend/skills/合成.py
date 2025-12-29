"""
技能: 合成
描述: 合成指定物品，自动处理工作台和配方
"""

async def 合成(bot, itemName, count=1):
    """
    合成指定物品
    
    流程：
    1. 查看物品配方（通过listRecipes）
    2. 检查是否需要工作台
    3. 如果需要工作台，先找到或制作工作台
    4. 检查材料是否足够
    5. 执行合成
    
    Args:
        bot: BotAPI实例
        itemName: 要合成的物品名称（如 oak_planks, stick, crafting_table, wooden_pickaxe）
        count: 合成数量，默认1
    
    Returns:
        合成结果
    """
    bot.log(f"开始合成: {itemName} x {count}")
    
    # 常见的2x2配方（不需要工作台）
    simple_recipes = {
        "oak_planks": {"材料": {"oak_log": 1}, "产出": 4},
        "birch_planks": {"材料": {"birch_log": 1}, "产出": 4},
        "spruce_planks": {"材料": {"spruce_log": 1}, "产出": 4},
        "jungle_planks": {"材料": {"jungle_log": 1}, "产出": 4},
        "acacia_planks": {"材料": {"acacia_log": 1}, "产出": 4},
        "dark_oak_planks": {"材料": {"dark_oak_log": 1}, "产出": 4},
        "stick": {"材料": {"oak_planks": 2}, "产出": 4},  # 任意木板都行
        "crafting_table": {"材料": {"oak_planks": 4}, "产出": 1},
    }
    
    # 需要工作台的3x3配方
    table_recipes = {
        "wooden_pickaxe": {"材料": {"oak_planks": 3, "stick": 2}, "产出": 1},
        "wooden_axe": {"材料": {"oak_planks": 3, "stick": 2}, "产出": 1},
        "wooden_shovel": {"材料": {"oak_planks": 1, "stick": 2}, "产出": 1},
        "wooden_sword": {"材料": {"oak_planks": 2, "stick": 1}, "产出": 1},
        "wooden_hoe": {"材料": {"oak_planks": 2, "stick": 2}, "产出": 1},
        "stone_pickaxe": {"材料": {"cobblestone": 3, "stick": 2}, "产出": 1},
        "stone_axe": {"材料": {"cobblestone": 3, "stick": 2}, "产出": 1},
        "stone_shovel": {"材料": {"cobblestone": 1, "stick": 2}, "产出": 1},
        "stone_sword": {"材料": {"cobblestone": 2, "stick": 1}, "产出": 1},
        "stone_hoe": {"材料": {"cobblestone": 2, "stick": 2}, "产出": 1},
        "iron_pickaxe": {"材料": {"iron_ingot": 3, "stick": 2}, "产出": 1},
        "iron_axe": {"材料": {"iron_ingot": 3, "stick": 2}, "产出": 1},
        "iron_shovel": {"材料": {"iron_ingot": 1, "stick": 2}, "产出": 1},
        "iron_sword": {"材料": {"iron_ingot": 2, "stick": 1}, "产出": 1},
        "iron_hoe": {"材料": {"iron_ingot": 2, "stick": 2}, "产出": 1},
        "diamond_pickaxe": {"材料": {"diamond": 3, "stick": 2}, "产出": 1},
        "diamond_axe": {"材料": {"diamond": 3, "stick": 2}, "产出": 1},
        "diamond_shovel": {"材料": {"diamond": 1, "stick": 2}, "产出": 1},
        "diamond_sword": {"材料": {"diamond": 2, "stick": 1}, "产出": 1},
        "diamond_hoe": {"材料": {"diamond": 2, "stick": 2}, "产出": 1},
        "furnace": {"材料": {"cobblestone": 8}, "产出": 1},
        "chest": {"材料": {"oak_planks": 8}, "产出": 1},
        "torch": {"材料": {"coal": 1, "stick": 1}, "产出": 4},
        "ladder": {"材料": {"stick": 7}, "产出": 3},
        "fence": {"材料": {"oak_planks": 4, "stick": 2}, "产出": 3},
        "boat": {"材料": {"oak_planks": 5}, "产出": 1},
        "bowl": {"材料": {"oak_planks": 3}, "产出": 4},
        "bucket": {"材料": {"iron_ingot": 3}, "产出": 1},
        "compass": {"材料": {"iron_ingot": 4, "redstone": 1}, "产出": 1},
        "fishing_rod": {"材料": {"stick": 3, "string": 2}, "产出": 1},
        "bed": {"材料": {"oak_planks": 3, "white_wool": 3}, "产出": 1},
        "shield": {"材料": {"oak_planks": 6, "iron_ingot": 1}, "产出": 1},
    }
    
    # 检查是否是已知配方
    needs_table = False
    recipe_info = None
    
    if itemName in simple_recipes:
        recipe_info = simple_recipes[itemName]
        needs_table = False
        bot.log(f"{itemName} 是2x2配方，不需要工作台")
    elif itemName in table_recipes:
        recipe_info = table_recipes[itemName]
        needs_table = True
        bot.log(f"{itemName} 是3x3配方，需要工作台")
    else:
        # 未知配方，尝试直接调用craft
        bot.log(f"未知配方，尝试直接合成 {itemName}")
        result = await bot.craft(itemName, count)
        return result
    
    # 检查背包材料
    inventory = await bot.viewInventory()
    items_dict = {}
    for item in inventory.get("inventory", []):
        items_dict[item["name"]] = items_dict.get(item["name"], 0) + item["count"]
    
    bot.log(f"当前背包: {items_dict}")
    
    # 计算需要合成几次（考虑产出数量）
    output_per_craft = recipe_info["产出"]
    craft_times = (count + output_per_craft - 1) // output_per_craft  # 向上取整
    
    # 检查材料是否足够
    missing = []
    for material, needed_per_craft in recipe_info["材料"].items():
        needed_total = needed_per_craft * craft_times
        have = items_dict.get(material, 0)
        if have < needed_total:
            missing.append(f"{material}: 需要{needed_total}个，只有{have}个")
    
    if missing:
        bot.log(f"材料不足: {missing}")
        await bot.chat(f"材料不够喵~ {', '.join(missing)}")
        return {
            "success": False,
            "message": f"材料不足: {', '.join(missing)}",
            "missing": missing
        }
    
    # 如果需要工作台
    if needs_table:
        # 先找工作台
        table = await bot.findCraftingTable(32)
        
        if not table.get("found"):
            bot.log("没有找到工作台，检查背包是否有")
            
            # 检查背包是否有工作台
            if items_dict.get("crafting_table", 0) > 0:
                bot.log("背包有工作台，放置它")
                # 获取当前位置并放置工作台
                pos = await bot.getPosition()
                place_result = await bot.placeBlock("crafting_table", 
                    int(pos["x"]) + 1, int(pos["y"]), int(pos["z"]))
                if not place_result.get("success"):
                    return {
                        "success": False,
                        "message": f"放置工作台失败: {place_result.get('message')}"
                    }
                await bot.chat("放好工作台啦喵~")
            else:
                # 需要先合成工作台
                bot.log("需要先合成工作台")
                await bot.chat("需要先做个工作台喵~")
                
                # 递归调用合成工作台
                table_result = await 合成(bot, "crafting_table", 1)
                if not table_result.get("success"):
                    return table_result
                
                # 放置工作台
                pos = await bot.getPosition()
                await bot.placeBlock("crafting_table", 
                    int(pos["x"]) + 1, int(pos["y"]), int(pos["z"]))
        else:
            # 走到工作台附近
            table_pos = table["position"]
            bot.log(f"找到工作台在 ({table_pos['x']}, {table_pos['y']}, {table_pos['z']})")
            
            # 检查距离
            pos = await bot.getPosition()
            dx = pos["x"] - table_pos["x"]
            dy = pos["y"] - table_pos["y"]
            dz = pos["z"] - table_pos["z"]
            distance = (dx*dx + dy*dy + dz*dz) ** 0.5
            
            if distance > 4:
                bot.log("走近工作台...")
                await bot.goTo(table_pos["x"], table_pos["y"], table_pos["z"])
    
    # 执行合成
    bot.log(f"开始合成 {itemName} x {count}")
    await bot.chat(f"合成 {itemName} 中...")
    
    result = await bot.craft(itemName, count)
    
    if result.get("success"):
        await bot.chat(f"合成成功喵~ {itemName} x {count}")
        return {
            "success": True,
            "message": f"成功合成 {itemName} x {count}",
            "crafted": count
        }
    else:
        await bot.chat(f"合成失败了喵... {result.get('message')}")
        return {
            "success": False,
            "message": result.get("message", "合成失败")
        }