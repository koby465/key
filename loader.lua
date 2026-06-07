-- Key Auth Loader
-- Usage:
--   script_key = "KA-xxxx"
--   loadstring(game:HttpGet("https://key-lbyl.onrender.com/loader"))()

local API_URL = "https://key-lbyl.onrender.com"
local HttpService = game:GetService("HttpService")

-- Read key from global set by user
local key = (getgenv and getgenv().script_key) or script_key or ""
key = tostring(key):gsub("%s+", "")

if key == "" or key == "nil" then
    error("[Auth] Set your key first: script_key = 'KA-...'")
end

-- Get HWID
local hwid = gethwid()
if not hwid or hwid == "" then
    error("[Auth] Failed to get HWID.")
end

-- Auth request
local body = HttpService:JSONEncode({ key = key, hwid = hwid })

local success, response = pcall(function()
    return request({
        Url    = API_URL .. "/auth",
        Method = "POST",
        Headers = { ["Content-Type"] = "application/json" },
        Body   = body
    })
end)

if not success then
    error("[Auth] Could not reach auth server. Try again.")
end

local ok, data = pcall(function()
    return HttpService:JSONDecode(response.Body)
end)

if not ok or not data then
    error("[Auth] Invalid server response.")
end

if not data.success then
    error("[Auth] " .. (data.error or "Authentication failed"))
end

-- Run protected script
local fn, err = loadstring(data.script)
if not fn then
    error("[Auth] Script error: " .. tostring(err))
end

fn()
