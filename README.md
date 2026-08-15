# local-llm-mcp

[![CI](https://github.com/kuotunyu/local-llm-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/kuotunyu/local-llm-mcp/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![MCP SDK](https://img.shields.io/badge/MCP%20SDK-1.x-8A2BE2)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

本專案為遵循 Model Context Protocol (MCP) 規範實作之 local-first LLM 委派伺服器：文件摘要、語言翻譯、結構化 JSON 抽取等 private tools 只呼叫設定的 Ollama endpoint；預設 `OLLAMA_HOST=http://127.0.0.1:11434`，因此模型流量留在本機。`web_search` 則是明確標示、需另外設定金鑰才可使用的 opt-in 外部工具，會將查詢送往 Felo API。系統支援 stdio 與 Streamable HTTP 雙傳輸通道、HTTP Bearer API Key 驗證、MCP 進度回報 (Progress reporting) 與四款主流 Client 整合。完整邊界見 [SECURITY.md](SECURITY.md)。

> **環境與相容性**：已完成 Claude Desktop、Claude Code、LM Studio 與 Antigravity CLI 四大 Client 之真實工具呼叫與相容性驗證。

---

## 系統介面與 Client 展示

### 1. Claude Desktop (Windows, stdio via wsl.exe)

| 連線狀態與 Connector 清單 | 工具呼叫實測 (Tool Call) |
|:---:|:---:|
| <img src="docs/screenshots/claude-desktop/connectors-list.png" height="280" alt="Claude Desktop Connectors 清單"> | <img src="docs/screenshots/claude-desktop/tool-call-success.png" height="280" alt="Claude Desktop Tool Call 實測"> |

### 2. Claude Code (WSL2 / Windows)

| 連線狀態與 Connector 清單 | 工具呼叫實測 (Tool Call) |
|:---:|:---:|
| <img src="docs/screenshots/claude-code/mcp-list.png" height="260" alt="Claude Code MCP List"> | <img src="docs/screenshots/claude-code/tool-call-success.png" height="260" alt="Claude Code Tool Call 實測"> |

### 3. LM Studio (Windows, Streamable HTTP + Key)

| 連線狀態與 Connector 清單 | 工具呼叫實測 (Tool Call) |
|:---:|:---:|
| <img src="docs/screenshots/lm-studio/integrations-panel.png" height="280" alt="LM Studio Integrations 面板"> | <img src="docs/screenshots/lm-studio/tool-call-success.png" height="280" alt="LM Studio Tool Call 實測"> |

### 4. Antigravity CLI (WSL2, Streamable HTTP + Key)

| 連線狀態與 Connector 清單 | 工具呼叫實測 (Tool Call) |
|:---:|:---:|
| <img src="docs/screenshots/antigravity-cli/mcp-list.png" height="260" alt="Antigravity CLI MCP List"> | <img src="docs/screenshots/antigravity-cli/tool-call-success.png" height="260" alt="Antigravity CLI Tool Call 實測"> |

---

## 系統核心機制

1. **MCP 全功能 Primitive 覆蓋**：
   實作 7 個 Tools (6 純本機 + 1 雲端搜尋隱私分流)、1 個 Resource (`models://local`) 與 2 個 Prompts 範本。
2. **雙 Transport 通道與標準驗證**：
   支援傳統 `stdio` 通道，以及基於官方 `TokenVerifier` 與 `AuthSettings` 之 `Streamable HTTP` 通道，防止未授權存取。
3. **分段 Map-Reduce 摘要與 Progress 回報**：
   長文本摘要自動按段落/句子邊界切分 chunk，透過 map-reduce 進行逐段摘要與合併，並經由 MCP Stream 即時回報進度。
4. **模型輸出非執行邊界與輸入限制**：
   模型輸出只作為資料回傳，不因內容看起來像 shell、Python、URL 或工具指令就由 server 自動執行；這是 non-execution boundary，不宣稱能解決所有 prompt injection。各工具另配置輸入長度限制與明確的 local／external routing 邊界。

---

## 系統架構與通訊協定

### 1. 系統硬體與拓撲架構

```mermaid
%%{init: {'themeVariables': {'fontSize': '20px'}}}%%
flowchart TD
    subgraph Clients ["MCP Client 端點 (Windows / WSL2)"]
        CD["Claude Desktop (Windows)<br/>stdio via wsl.exe"]
        CC["Claude Code (WSL2 / Windows)<br/>stdio / Streamable HTTP + Key"]
        LMS["LM Studio (Windows)<br/>Streamable HTTP + Key"]
        AG["Antigravity CLI (WSL2)<br/>stdio / Streamable HTTP + Key"]
    end

    subgraph Server ["local-llm-mcp 核心伺服器 (WSL2)"]
        API["FastMCP 網關 & TokenVerifier 驗證"]
        TOOLS["7 Tools / 1 Resource / 2 Prompts"]
        API --> TOOLS
    end

    subgraph Backend ["地端推論與外部 API"]
        Ollama[("Ollama :11434 (RTX 4090)<br/>TAIDE / Llama3 8B")]
        Felo[("Felo Chat API (雲端選配)<br/>僅公開知識搜尋分流")]
    end

    CD & CC & LMS & AG --> API
    TOOLS --> Ollama
    TOOLS -.->|"web_search (隱私分流)"| Felo

    style API fill:#fff9db,stroke:#f59f00,stroke-width:2px
    style Ollama fill:#e7f5ff,stroke:#1971c2,stroke-width:2px
```

### 2. MCP 傳輸協定與認證時序 (Protocol & Progress Sequence)

```mermaid
%%{init: {'themeVariables': {'fontSize': '20px'}}}%%
sequenceDiagram
    autonumber
    actor User as 使用者 / LLM Client
    participant Client as MCP Client<br/>(Claude / LM Studio / AG)
    participant Gateway as local-llm-mcp Gateway<br/>(TokenVerifier Auth)
    participant Engine as 地端推論引擎<br/>(Ollama RTX 4090)

    User->>Client: 發起長文摘要請求
    Client->>Gateway: POST /mcp (Bearer API Key)
    Note over Gateway: 驗證 Authorization Header<br/>與 TokenVerifier 白名單
    Gateway-->>Client: 200 OK (Streamable HTTP Session Initiated)

    Client->>Gateway: JSON-RPC Call: summarize_private(text)
    Note over Gateway: private tool 只呼叫 configured Ollama endpoint<br/>預設 127.0.0.1 為本機路徑

    loop 分段推論與 Progress 即時回報
        Gateway->>Engine: Generate Chunk Summary
        Engine-->>Gateway: Partial Summary Output
        Gateway-->>Client: MCP Progress Notification (bytes_processed / total)
    end

    Gateway-->>Client: JSON-RPC Result: 最終整合摘要結果
    Client-->>User: 呈現完整摘要文字
```

---

## 功能與工具規格

### 1. Tools 工具清單

| 工具名稱 | 類型 | 功能說明與參數規範 |
|---|---|---|
| `ask_local` | 純本機 | 自由問答，直接傳送 Prompt 給本機 Ollama 模型 |
| `summarize_private` | 純本機 | 支援長文本 Map-Reduce 分段摘要與 Progress 進度回報 |
| `translate_private` | 純本機 | 中英雙向自動判斷翻譯 (`target_lang: "zh-TW" \| "en"`) |
| `extract_json` | 純本機 | 依呼叫端帶入之任意 JSON Schema 進行溫度為 0 之結構化抽取 (`format=`) |
| `list_local_models` | 純本機 | 列出地端 Ollama 已載入模型之參數尺寸、量化等級與 Context Window |
| `pull_model` | 純本機 | 下載 Ollama 模型並透過 MCP Progress 即時回報位元組進度 |
| `web_search` | 雲端選配 | **唯一外接 API 工具**：經 Felo Chat API 做即時網路搜尋，供模型進行公開與隱私分流 |

### 2. Resource 資源與 Prompts 範本

- **Resource (`models://local`)**：回傳地端 Ollama 模型清單快照 (REST GET 語意)。
- **Prompts 範本**：`summarize_for_report` (正式報告語氣) 與 `translate_formal` (正式書面語翻譯)。

---

## 系統相容性矩陣

| Client 平台 | 執行環境 | Transport 模式 | 認證機制 | 相容性測試結論 |
|---|---|---|---|---|
| **Claude Desktop** | Windows | `stdio` (via `wsl.exe`) | 系統層級權限 | 已通過完整 Tools / Resources 呼叫測試 |
| **Claude Code** | WSL2 / Windows | `stdio` / `HTTP` | Bearer API Key | 已通過指令列網關及工具整合驗證 |
| **LM Studio** | Windows | `Streamable HTTP` | Bearer API Key | 已通過 Integrations 面板與官方確認框驗證 |
| **Antigravity CLI** | WSL2 | `stdio` / `HTTP` | Bearer API Key | 已通過 `~/.gemini/config/mcp_config.json` 驗證 |

---

## 延遲量測與效能

評測環境：NVIDIA RTX 4090 (24GB VRAM)、WSL2、`num_ctx=8192`。比較 `cwchang/llama3-taide-lx-8b-chat-alpha1` (8B Q5_K_M) 與 `qwen2.5:3b` (3B)：

| 測試工具 | 輸入文字規模 | TAIDE (8B) 耗時 | Qwen2.5 (3B) 耗時 |
|---|---|---:|---:|
| `list_local_models` | N/A | **0.19s** | N/A |
| `ask_local` | 短文本 (~14 字) | 0.34s | 0.49s |
| `ask_local` | 長文本 (~500 字) | 1.72s | **0.62s** |
| `summarize_private` | 短文章 (單一 Chunk) | 0.58s | **0.23s** |
| `summarize_private` | 長文章 (1,332 字) | 1.21s | **0.63s** |
| `translate_private` | 單一段落 | 0.56s | **0.25s** |
| `extract_json` | 複雜 Schema (5 欄位 + Enum) | 0.54s | **0.35s** |

---

## 快速開始

需求：Windows 11 + WSL2、NVIDIA GPU、Python 3.11+、Ollama、`uv`。

### 1. 於 WSL2 啟動 Ollama 服務與模型

```bash
# 啟動 Ollama 服務與拉取 TAIDE 8B 台灣在地化模型
ollama serve &
ollama pull cwchang/llama3-taide-lx-8b-chat-alpha1
```

### 2. 安裝與啟動 MCP Server

```bash
# 複製專案與安裝依賴
git clone https://github.com/kuotunyu/local-llm-mcp.git
cd local-llm-mcp
uv sync

# 設定環境變數
cp .env.example .env

# 啟動 stdio 傳輸通道 (預設)
uv run local-llm-mcp

# 啟動 Streamable HTTP 傳輸通道 (需於 .env 設定 LOCAL_LLM_MCP_API_KEY)
uv run local-llm-mcp --transport streamable-http
```

---

## Client 配置教學

### 1. Claude Desktop 配置 (Windows stdio via `wsl.exe`)

編輯 `%APPDATA%\Claude\claude_desktop_config.json`：

```jsonc
{
  "mcpServers": {
    "local-llm-mcp": {
      "command": "wsl.exe",
      "args": [
        "-d", "<WSL_DISTRO_NAME>",
        "--",
        "/home/<user>/local-llm-mcp/.venv/bin/python3", "-m", "local_llm_mcp.server"
      ]
    }
  }
}
```

### 2. Claude Code 配置 (Streamable HTTP + API Key)

```bash
claude mcp add --transport http local-llm-mcp http://127.0.0.1:8000/mcp \
  --header "Authorization: Bearer <YOUR_API_KEY>"
```

### 3. LM Studio 配置 (Windows Streamable HTTP)

編輯 `%USERPROFILE%\.lmstudio\mcp.json`：

```jsonc
{
  "mcpServers": {
    "local-llm-mcp": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer <YOUR_API_KEY>"
      }
    }
  }
}
```

---

## 環境變數與安全配置

| 環境變數 | 預設設定值 | 功能說明與安全防護 |
|---|---|---|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama 服務位址；若改成遠端 endpoint，private tools 的資料邊界也會跟著改變 |
| `LOCAL_LLM_MCP_DEFAULT_MODEL` | `cwchang/llama3-taide-lx-8b-chat-alpha1` | 預設 LLM 模型 |
| `LOCAL_LLM_MCP_MAX_PROMPT_CHARS` | `8000` | 一般問答與抽取之輸入字數上限 |
| `LOCAL_LLM_MCP_MAX_SUMMARIZE_CHARS` | `200000` | 摘要任務之輸入字數上限 |
| `LOCAL_LLM_MCP_API_KEY` | (HTTP 必填) | Streamable HTTP 之 Bearer Token 驗證密鑰；stdio 不使用此 application-layer auth |
| `LOCAL_LLM_MCP_HTTP_HOST` | `127.0.0.1` | Streamable HTTP 預設綁定 IP |
| `LOCAL_LLM_MCP_EXTRA_ALLOWED_HOSTS` | (空) | 額外 Host/Origin allow-list；不會自行改變 HTTP bind address |
| `FELO_API_KEY` | (空) | 啟用 `web_search` 的外部 Felo API；未設定時該工具 fail closed |

更多 trust / privacy boundary 請見 [SECURITY.md](SECURITY.md)。

---

## 授權與聲明

本專案採用 [MIT License](LICENSE)。
