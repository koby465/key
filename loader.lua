-- ╔══════════════════════════════════════════╗
-- ║         Key Auth Loader (Potassium)      ║
-- ╚══════════════════════════════════════════╝

local API_URL = "https://YOUR-APP.railway.app"  -- replace with your Railway URL

-- ── Get HWID ──────────────────────────────────────────────────────────────
local hwid = getmachineid()
if not hwid or hwid == "" then
    error("[Auth] Failed to get HWID. Are you on Potassium?")
end

-- ── Prompt for key ────────────────────────────────────────────────────────
-- You can replace this with a saved key from writefile/readfile
local key

local keyFile = "auth_key.txt"

if isfile(keyFile) then
    key = readfile(keyFile):gsub("%s+", "")  -- trim whitespace
else
    -- First time: ask user to paste key
    -- (Use your GUI's input box here instead if you have one)
    error("[Auth] No key found. Create a file called 'auth_key.txt' in your executor's workspace folder and paste your key in it.")
end

if not key or key == "" then
    error("[Auth] Key file is empty.")
end

-- ── Send auth request ─────────────────────────────────────────────────────
local HttpService = game:GetService("HttpService")

local body = HttpService:JSONEncode({
    key  = key,
    hwid = hwid
})

local success, response = pcall(function()
    return request({
        Url    = API_URL .. "/auth",
        Method = "POST",
        Headers = { ["Content-Type"] = "application/json" },
        Body   = body
    })
end)

if not success then
    error("[Auth] Could not reach auth server. Check your internet or the server may be down.")
end

-- ── Parse response ────────────────────────────────────────────────────────
local ok, data = pcall(function()
    return HttpService:JSONDecode(response.Body)
end)

if not ok or not data then
    error("[Auth] Invalid response from server.")
end

if not data.success then
    local err = data.error or "Unknown error"
    error("[Auth] Authentication failed: " .. err)
end

-- ── Execute protected script ──────────────────────────────────────────────
local script_src = data.script

if not script_src or script_src == "" then
    error("[Auth] Server returned empty script.")
end

local fn, loadErr = loadstring(script_src)
if not fn then
    error("[Auth] Failed to load script: " .. tostring(loadErr))
end

fn()
