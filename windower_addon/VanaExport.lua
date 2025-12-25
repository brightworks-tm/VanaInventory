--[[
    VanaExport - Windower Addon for VanaInventory
    実行中のFFXIからインベントリ・装備データをJSONエクスポート
]]

_addon.name = 'VanaExport'
_addon.author = 'VanaInventory'
_addon.version = '1.0.0'
_addon.commands = {'vanaexport', 'vex'}

require('logger')
local packets = require('packets')
local res = require('resources')
local files = require('files')
-- extdataライブラリでオーグメント解析
local extdata = nil
local ok_ext, ext_mod = pcall(require, 'extdata')
if ok_ext then extdata = ext_mod end

-- JSONライブラリ (json or rapidjson)
local json = nil
local ok, mod = pcall(require, 'json')
if ok then json = mod end

-- rapidjson fallback
if not json or not (type(json) == 'table' and json.encode) then
    local ok2, rj = pcall(require, 'rapidjson')
    if ok2 and rj then
        json = rj
    end
end

-- 簡易JSONエンコーダ（数値/文字列/真偽/配列/テーブルのみ対応）
local function build_fallback_encoder()
    local function escape_str(s)
        s = s:gsub('\\', '\\\\')
        s = s:gsub('"', '\\"')
        s = s:gsub('\n', '\\n')
        s = s:gsub('\r', '\\r')
        s = s:gsub('\t', '\\t')
        return '"' .. s .. '"'
    end

    local function is_array(t)
        local i = 0
        for _ in pairs(t) do
            i = i + 1
            if t[i] == nil then return false end
        end
        return true
    end

    local function encode_value(v)
        local vt = type(v)
        if vt == 'nil' then
            return 'null'
        elseif vt == 'number' or vt == 'boolean' then
            return tostring(v)
        elseif vt == 'string' then
            return escape_str(v)
        elseif vt == 'table' then
            if is_array(v) then
                local parts = {}
                for i = 1, #v do
                    parts[#parts+1] = encode_value(v[i])
                end
                return '[' .. table.concat(parts, ',') .. ']'
            else
                local parts = {}
                for k, val in pairs(v) do
                    parts[#parts+1] = escape_str(tostring(k)) .. ':' .. encode_value(val)
                end
                return '{' .. table.concat(parts, ',') .. '}'
            end
        else
            return 'null'
        end
    end

    return encode_value
end

local json_encode = nil

-- 1) json.encode があれば使う
if json and type(json) == 'table' and type(json.encode) == 'function' then
    json_encode = function(data) return json.encode(data) end
-- 2) json が関数ならそれを使う
elseif type(json) == 'function' then
    json_encode = json
end

-- 3) ここまででエンコーダが無い場合はフォールバックを作成
if not json_encode then
    local fallback = build_fallback_encoder()
    json_encode = fallback
end

-- 設定
local config = {
    output_path = 'data/',  -- Windowerのaddons/VanaExport/data/に出力
    auto_export = false,    -- ゾーン移動時に自動エクスポート
}

-- ストレージID定義
local STORAGE_NAMES = {
    [0] = 'Inventory',
    [1] = 'Safe',
    [2] = 'Storage',
    [3] = 'Temporary',
    [4] = 'Locker',
    [5] = 'Satchel',
    [6] = 'Sack',
    [7] = 'Case',
    [8] = 'Wardrobe',
    [9] = 'Safe 2',
    [10] = 'Wardrobe 2',
    [11] = 'Wardrobe 3',
    [12] = 'Wardrobe 4',
    [13] = 'Wardrobe 5',
    [14] = 'Wardrobe 6',
    [15] = 'Wardrobe 7',
    [16] = 'Wardrobe 8',
}

-- 装備スロット名定義
-- Windower APIのキー名 -> 出力用のスロット名
local EQUIP_SLOT_NAMES = {
    [0] = {api = 'main', output = 'main'},
    [1] = {api = 'sub', output = 'sub'},
    [2] = {api = 'range', output = 'range'},
    [3] = {api = 'ammo', output = 'ammo'},
    [4] = {api = 'head', output = 'head'},
    [5] = {api = 'body', output = 'body'},
    [6] = {api = 'hands', output = 'hands'},
    [7] = {api = 'legs', output = 'legs'},
    [8] = {api = 'feet', output = 'feet'},
    [9] = {api = 'neck', output = 'neck'},
    [10] = {api = 'waist', output = 'waist'},
    [11] = {api = 'left_ear', output = 'ear1'},
    [12] = {api = 'right_ear', output = 'ear2'},
    [13] = {api = 'left_ring', output = 'ring1'},
    [14] = {api = 'right_ring', output = 'ring2'},
    [15] = {api = 'back', output = 'back'},
}

-- アイテム情報を取得
local function get_item_info(bag, index)
    local items = windower.ffxi.get_items(bag)
    if not items or not items[index] then
        return nil
    end
    
    local item = items[index]
    if item.id == 0 then
        return nil
    end
    
    local item_res = res.items[item.id]
    local name_ja = item_res and item_res.name or 'Unknown'
    local name_en = item_res and item_res.en or 'Unknown'
    
    -- 詳細情報取得
    -- items.luaの type: 4=Weapon, 5=Armor, 他=素材等
    local item_type = item_res and item_res.type or nil
    local item_slot = item_res and item_res.slots or nil  -- 装備スロット（ビットマスク）
    local item_skill = item_res and item_res.skill or nil  -- スキルタイプ（武器の場合）
    local item_level = item_res and item_res.level or nil
    local item_level_ilvl = item_res and item_res.item_level or nil
    local jobs_raw = item_res and item_res.jobs or nil
    local flags = item_res and item_res.flags or nil
    
    -- 実際のアイテムタイプを決定（武器はskill、防具はslots）
    local actual_item_type = nil
    if item_type == 4 then
        -- 武器の場合、skillがアイテムタイプ
        actual_item_type = item_skill
    elseif item_type == 5 then
        -- 防具の場合、slotsがアイテムタイプ
        actual_item_type = item_slot
    end
    
    -- item_categoryをUI用に変換（4=Weapon, 5=Armor -> 0=Weapon, 1=Armor）
    local item_category = nil
    if item_type == 4 then
        item_category = 0  -- Weapon
    elseif item_type == 5 then
        item_category = 1  -- Armor
    else
        item_category = item_type  -- その他はそのまま
    end
    
    -- jobsを配列形式に変換
    local jobs = nil
    if jobs_raw then
        if type(jobs_raw) == 'table' then
            -- Windower resources.luaは数値キーの辞書を返す: {1=true, 7=true, 22=true}
            local job_list = {}
            for job_id, enabled in pairs(jobs_raw) do
                if enabled and type(job_id) == 'number' then
                    table.insert(job_list, job_id)
                end
            end
            -- ジョブIDでソート
            table.sort(job_list)
            if #job_list > 0 then
                jobs = job_list
            end
        elseif type(jobs_raw) == 'number' then
            -- 数値（ビットフラグ）の場合、ジョブリストに展開
            local job_list = {}
            for i = 1, 22 do
                if bit.band(jobs_raw, bit.lshift(1, i)) ~= 0 then
                    table.insert(job_list, i)
                end
            end
            if #job_list > 0 then
                jobs = job_list
            end
        end
    end
    
    -- 説明文取得
    local desc_res = res.item_descriptions[item.id]
    local desc_ja = desc_res and desc_res.ja or nil
    local desc_en = desc_res and desc_res.en or nil
    
    -- extdataをHex文字列に変換
    local extdata_hex = nil
    if item.extdata then
        extdata_hex = item.extdata:hex()
    end
    
    -- オーグメント解析
    local augments = nil
    if extdata and item.extdata then
        local ok, decoded = pcall(extdata.decode, item)
        if ok and decoded and decoded.augments then
            -- 有効なオーグメントのみ抽出
            augments = {}
            for _, aug in ipairs(decoded.augments) do
                if aug and aug ~= '' and aug ~= 'none' then
                    table.insert(augments, aug)
                end
            end
            if #augments == 0 then augments = nil end
        end
    end
    
    return {
        id = item.id,
        name = name_ja,
        name_en = name_en,
        count = item.count,
        slot = index,
        extdata = extdata_hex,
        augments = augments,
        description = desc_ja,
        description_en = desc_en,
        -- 詳細情報
        item_type = actual_item_type,  -- 実際のアイテムタイプ（武器はskill、防具はslots）
        item_category = item_category,  -- カテゴリ（0=Weapon, 1=Armor, その他=素材等）
        level = item_level,
        item_level = item_level_ilvl,
        jobs = jobs,
        flags = flags,
    }
end

-- ストレージ全体を取得
local function get_storage(bag_id)
    local items_data = windower.ffxi.get_items(bag_id)
    if not items_data then
        return nil
    end
    
    local items = {}
    local max_slots = items_data.max or 80
    
    for i = 1, max_slots do
        local item = get_item_info(bag_id, i)
        if item then
            table.insert(items, item)
        end
    end
    
    return {
        name = STORAGE_NAMES[bag_id] or ('Bag' .. bag_id),
        bag_id = bag_id,
        max_slots = max_slots,
        items = items,
    }
end

-- 現在の装備を取得
local function get_current_equipment()
    local equipment = windower.ffxi.get_items().equipment
    if not equipment then
        return nil
    end
    
    local equip_data = {}
    
    for slot_id, slot_info in pairs(EQUIP_SLOT_NAMES) do
        local api_name = slot_info.api
        local output_name = slot_info.output
        
        local bag = equipment[api_name .. '_bag']
        local index = equipment[api_name]
        
        if bag and index and index > 0 then
            local item = get_item_info(bag, index)
            if item then
                item.equip_slot = output_name
                item.equip_slot_id = slot_id
                equip_data[output_name] = item
            end
        end
    end
    
    return equip_data
end

-- プレイヤー情報を取得
local function get_player_info()
    local player = windower.ffxi.get_player()
    if not player then
        return nil
    end
    
    -- 基本情報
    local info = {
        name = player.name,
        id = player.id,
        main_job = player.main_job,
        main_job_level = player.main_job_level,
        sub_job = player.sub_job,
        sub_job_level = player.sub_job_level,
        job_points = player.job_points,
        merits = player.merits,
    }

    -- Vitals (HP, MP, TP)
    if player.vitals then
        info.hp = player.vitals.hp
        info.max_hp = player.vitals.max_hp
        info.hpp = player.vitals.hpp
        info.mp = player.vitals.mp
        info.max_mp = player.vitals.max_mp
        info.mpp = player.vitals.mpp
        info.tp = player.vitals.tp
    end

    -- Stats (STR, DEX, etc.)
    if player.stats then
        info.stats = {
            str = player.stats.str,
            dex = player.stats.dex,
            vit = player.stats.vit,
            agi = player.stats.agi,
            int = player.stats.int,
            mnd = player.stats.mnd,
            chr = player.stats.chr,
        }
    end

    -- 攻撃力・防御力 (もし取得できれば)
    -- Windowerのバージョンや環境によっては player.stats に含まれる場合や
    -- player 直下にある場合、あるいは取得できない場合がある
    if player.p_attack then info.attack = player.p_attack end -- 仮のキー名
    if player.p_defense then info.defense = player.p_defense end -- 仮のキー名
    
    -- 注意: 標準APIでは攻撃力・防御力が直接取れないことが多い
    -- ここではプレースホルダーとして 0 を入れておくか、
    -- 上記のように存在チェックを行う
    if not info.attack then info.attack = 0 end
    if not info.defense then info.defense = 0 end

    return info
end

-- 全データをエクスポート
local function export_all()
    local player = get_player_info()
    if not player then
        log('プレイヤー情報が取得できません')
        return false
    end
    
    local data = {
        version = '1.0',
        export_time = os.date('%Y-%m-%d %H:%M:%S'),
        player = player,
        equipment = get_current_equipment(),
        storages = {},
    }
    
    -- 全ストレージを取得
    for bag_id, bag_name in pairs(STORAGE_NAMES) do
        local storage = get_storage(bag_id)
        if storage and #storage.items > 0 then
            data.storages[bag_name] = storage
        end
    end
    
    -- JSON出力
    local filename = config.output_path .. player.name .. '_inventory.json'
    local f = files.new(filename)
    
    if f then
        f:write(json_encode(data))
        log('エクスポート完了: ' .. filename)
        return true
    else
        log('ファイル作成に失敗: ' .. filename)
        return false
    end
end

-- 装備のみエクスポート
local function export_equipment()
    local player = get_player_info()
    if not player then
        log('プレイヤー情報が取得できません')
        return false
    end
    
    local data = {
        version = '1.0',
        export_time = os.date('%Y-%m-%d %H:%M:%S'),
        player = player,
        equipment = get_current_equipment(),
    }
    
    local filename = config.output_path .. player.name .. '_equipment.json'
    local f = files.new(filename)
    
    if f then
        f:write(json_encode(data))
        log('装備エクスポート完了: ' .. filename)
        return true
    else
        log('ファイル作成に失敗: ' .. filename)
        return false
    end
end

-- コマンドハンドラ
windower.register_event('addon command', function(command, ...)
    command = command and command:lower() or 'help'
    
    if command == 'all' or command == 'a' then
        export_all()
    elseif command == 'equip' or command == 'e' then
        export_equipment()
    elseif command == 'auto' then
        config.auto_export = not config.auto_export
        log('自動エクスポート: ' .. (config.auto_export and 'ON' or 'OFF'))
    elseif command == 'help' or command == 'h' then
        log('=== VanaExport コマンド ===')
        log('//vex all   - 全インベントリをエクスポート')
        log('//vex equip - 現在の装備のみエクスポート')
        log('//vex auto  - ゾーン移動時の自動エクスポート切替')
    else
        log('不明なコマンド: ' .. command .. ' (//vex help でヘルプ表示)')
    end
end)

-- ゾーン変更時の自動エクスポート
windower.register_event('zone change', function(new_id, old_id)
    if config.auto_export then
        -- 少し待ってからエクスポート（データ読み込み待ち）
        coroutine.schedule(function()
            export_all()
        end, 5)
    end
end)

-- 初期化
windower.register_event('load', function()
    log('VanaExport loaded. //vex help でヘルプ表示')
end)
