-- 汎用の MAME 実行スクリプト（hknroms/gradius3 の g3run.lua を一般化したもの）
-- 画面・音なしで高速に回し、入力を与え、RAM を見て、画像やメモリを保存する。lua/run.sh から使う。
--
-- 環境変数:
--   SEQ="f:KEY,..."     f フレーム目にキーを押す（HOLD フレーム後に離す。既定 8）
--   HOLDK="f:KEY:len"   押す長さを指定
--     KEY: COIN COIN2 START START2 U D L R B1 B2 B3 B4 SVC  （MAME の入力名で探すので、どのドライバでも使える）
--   POKE="f:addr:val[:w]"  f フレーム目に CPU 空間へ書く（16進、:w で16bit）
--   WATCH="addr,addr"   値が変わったフレームを表示（8bit）
--   CPU=":maincpu"      POKE・WATCH・DUMP の対象 CPU（既定 :maincpu）
--   SNAP="s:e:i"        s〜e フレームの i ごとにスクリーンショット（-snapshot_directory に保存）
--   DUMPAT="f,f"  DUMP="name:lo:hi,..."  f フレーム目にメモリを <OUT>_<name>_<f>.bin へ保存（ROM 由来なので公開しない）
--   OUTLOG=file   END=終了フレーム（既定 3000）
local m = manager.machine
local function find_field(name)
  for _, port in pairs(m.ioport.ports) do
    for fname, f in pairs(port.fields) do if fname == name then return f end end
  end
end
local KEYNAME = { COIN = "Coin 1", COIN2 = "Coin 2", START = "1 Player Start", START2 = "2 Players Start",
  U = "P1 Up", D = "P1 Down", L = "P1 Left", R = "P1 Right",
  B1 = "P1 Button 1", B2 = "P1 Button 2", B3 = "P1 Button 3", B4 = "P1 Button 4", SVC = "Service Mode" }
local F = {}
for k, n in pairs(KEYNAME) do F[k] = find_field(n) end
local cpu = m.devices[os.getenv("CPU") or ":maincpu"].spaces["program"]
local HOLD = tonumber(os.getenv("HOLD") or "8")
local press, release = {}, {}
local function at(t, f, v) t[f] = t[f] or {}; table.insert(t[f], v) end
for f, k in (os.getenv("SEQ") or ""):gmatch("(%d+):(%w+)") do f = tonumber(f); at(press, f, k); at(release, f + HOLD, k) end
for f, k, l in (os.getenv("HOLDK") or ""):gmatch("(%d+):(%w+):(%d+)") do f = tonumber(f); at(press, f, k); at(release, f + tonumber(l), k) end
local pokes = {}
for f, a, v, w in (os.getenv("POKE") or ""):gmatch("(%d+):(%x+):(%x+):?(w?)") do
  table.insert(pokes, { tonumber(f), tonumber(a, 16), tonumber(v, 16), w == "w" }) end
local watch = {}
for a in (os.getenv("WATCH") or ""):gmatch("[^,]+") do table.insert(watch, tonumber(a, 16)) end
local s0, s1, si = (os.getenv("SNAP") or "0:0:1"):match("(%d+):(%d+):(%d+)")
s0, s1, si = tonumber(s0), tonumber(s1), tonumber(si)
local END = tonumber(os.getenv("END") or "3000")
local dumpat = {}
for f in (os.getenv("DUMPAT") or ""):gmatch("%d+") do dumpat[tonumber(f)] = true end
local dumps = {}
for n, lo, hi in (os.getenv("DUMP") or ""):gmatch("(%w+):(%x+):(%x+)") do table.insert(dumps, { n, tonumber(lo, 16), tonumber(hi, 16) }) end
local OUT = os.getenv("DUMPPREFIX") or os.getenv("OUT") or "dump"
local logf = os.getenv("OUTLOG") and io.open(os.getenv("OUTLOG"), "w") or nil
local function P(...) local s = table.concat({ ... }, " "); if logf then logf:write(s, "\n") else print(s) end end
for k, n in pairs(KEYNAME) do
  if not F[k] and (os.getenv("SEQ") or ""):find(":" .. k) then P("注意: 入力 " .. n .. " がこのドライバに無い") end
end

local frame, last = 0, ""
KITNOTIF = emu.add_machine_frame_notifier(function()
  frame = frame + 1
  for _, k in ipairs(press[frame] or {}) do if F[k] then F[k]:set_value(1) end end
  for _, k in ipairs(release[frame] or {}) do if F[k] then F[k]:clear_value() end end
  for _, p in ipairs(pokes) do if p[1] == frame then
    if p[4] then cpu:write_u16(p[2], p[3]) else cpu:write_u8(p[2], p[3]) end end end
  if #watch > 0 then
    local t = {}
    for _, a in ipairs(watch) do t[#t + 1] = string.format("%x=%02x", a, cpu:read_u8(a)) end
    local s = table.concat(t, " ")
    if s ~= last then P(frame, s); last = s end
  end
  if dumpat[frame] then
    for _, d in ipairs(dumps) do
      local o = io.open(string.format("%s_%s_%d.bin", OUT, d[1], frame), "wb"); o:write(cpu:read_range(d[2], d[3], 8)); o:close()
    end
  end
  if frame >= s0 and frame <= s1 and (frame - s0) % si == 0 then m.video:snapshot() end
  if frame >= END then if logf then logf:close() end; m:exit() end
end)
