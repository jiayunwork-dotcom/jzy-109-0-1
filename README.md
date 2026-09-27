# Wheatstone Bridge Calculation Service（惠斯通电桥核算服务）

常驻进程的惠斯通电桥 HTTP 核算服务，只做电桥相关的两件事，无网页、无商城：

1. **正算**：给定四个桥臂电阻与桥源电压，求不平衡开路输出电压；
   可选给检流计内阻，按戴维南等效给出接表后的实际偏转（电流/端电压）。
2. **反解**：给定三个已知桥臂，按平衡条件 `r1·r3 = r2·r4` 闭式反推
   待测臂应取的阻值。

桥臂编号约定与电路图见 [`docs/bridge-model.md`](docs/bridge-model.md)。

## 技术栈与运行时

* Python **3.12**（锁定）、FastAPI、Uvicorn
* 纯 JSON over HTTP，无任何前端页面
* 预置的命名电桥档只存在进程内存中，跨重启不保留；各档四臂互相独立。

## 文件职责划分

| 文件 | 职责 |
|------|------|
| `app/divider.py` | 开路输出：两条分压支路的电位差 |
| `app/thevenin.py` | 接入检流计后的戴维南等效求解（V_th、R_th、Ig、Vg） |
| `app/balance.py` | 平衡条件与未知臂的闭式反解（与正算**不同文件**） |
| `app/registry.py` | 命名电桥档的登记/检索（进程内、线程安全、互相独立） |
| `app/validation.py` | 计算前的参数校验，拒绝时带明确 `reason` |
| `app/schemas.py` | HTTP 请求/响应模型 |
| `app/main.py` | FastAPI HTTP 层：仅收发请求与编排调用 |
| `tests/` | 物理关系、校验、注册表与 HTTP 端到端自动化测试 |

## 一键构建与运行（容器）

```bash
docker build -t wheatstone-bridge:1.0.0 .
docker run --rm -p 8000:8000 wheatstone-bridge:1.0.0
```

容器起来后两个核心接口即对外可用：`POST /bridge/output`、`POST /bridge/solve`。
交互式文档（由 FastAPI 自动生成，非交付的业务页面）在
`http://localhost:8000/docs`；健康检查 `GET /health`。

## 本地直接运行（开发/测试）

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
pytest -q
```

## 接口

### 1. 不平衡输出（可选接检流计）— `POST /bridge/output`

```bash
curl -s http://localhost:8000/bridge/output \
  -H 'content-type: application/json' \
  -d '{"source_voltage": 10.0,
       "arms": {"r1": 100, "r2": 100, "r3": 100, "r4": 150}}'
```

```json
{
  "arms": {"r1": 100.0, "r2": 100.0, "r3": 100.0, "r4": 150.0},
  "source_voltage": 10.0,
  "balanced": false,
  "open_circuit_voltage": 1.0,
  "branch_potentials": {"b": 6.0, "d": 5.0},
  "thevenin_resistance": 110.0,
  "galvanometer": null,
  "note": null
}
```

核对：`V_B = 10·150/(100+150) = 6.0`，`V_D = 10·100/(100+100) = 5.0`，
故 `V_out = 1.0 V`；`R_th = (100∥150)+(100∥100) = 60+50 = 110 Ω`。

带检流计时加 `galvanometer_resistance`（正阻值），响应中给出
`thevenin_voltage / thevenin_resistance / current / terminal_voltage`：

```bash
curl -s http://localhost:8000/bridge/output \
  -H 'content-type: application/json' \
  -d '{"source_voltage": 10.0,
       "arms": {"r1": 100, "r2": 100, "r3": 100, "r4": 150},
       "galvanometer_resistance": 250}'
```

**平衡例**（`r1·r3 = r2·r4`：100·300 = 150·200，各臂并不相等）：

```bash
curl -s http://localhost:8000/bridge/output \
  -H 'content-type: application/json' \
  -d '{"source_voltage": 12,
       "arms": {"r1": 100, "r2": 150, "r3": 300, "r4": 200}}'
# -> balanced: true, open_circuit_voltage: 0.0
```

`source_voltage = 0` 合法：直接返回零输出并在 `note` 标明，不算错误。

### 2. 反推待测臂 — `POST /bridge/solve`

`known_arms` 中给且仅给三个臂，缺哪个就解哪个：

```bash
curl -s http://localhost:8000/bridge/solve \
  -H 'content-type: application/json' \
  -d '{"known_arms": {"r1": 100, "r2": 200, "r4": 50}}'
```

```json
{
  "unknown_arm": "r3",
  "resistance": 100.0,
  "known_arms": {"r1": 100.0, "r2": 200.0, "r4": 50.0},
  "formula": "r3 = r2 * r4 / r1",
  "balance_residual": 0.0,
  "note": "closed-form solve from the balance condition r1*r3 = r2*r4 ..."
}
```

把 `resistance` 填回 `POST /bridge/output`，开路输出归零（自洽闭合）。

### 3. 命名电桥档（进程内，可反复调用）

```bash
curl -s -X POST http://localhost:8000/configs \
  -H 'content-type: application/json' \
  -d '{"name": "lab-equal",
       "arms": {"r1": 100, "r2": 100, "r3": 100, "r4": 100}}'

curl -s http://localhost:8000/bridge/output \
  -H 'content-type: application/json' \
  -d '{"source_voltage": 8.0, "config": "lab-equal"}'

curl -s http://localhost:8000/configs                 # 列出
curl -s http://localhost:8000/configs/lab-equal       # 查看
curl -s -X DELETE http://localhost:8000/configs/lab-equal
```

`arms` 与 `config` 二选一，不能同时给也不能都不给。两个电桥档各存
各的四臂，覆盖其中一个不会串到另一个。

## 非法输入（在计算前拦截，带原因）

统一返回 HTTP 400：`{"error": "invalid_input", "reason": "..."}`；
命名档不存在返回 404（`config_not_found`）。区分的情形包括：

* 任一桥臂（或检流计内阻）**不为正**（≤ 0、NaN、inf、非数值）——reason
  指出是哪个臂；
* **桥臂缺项**（少 r1..r4 中任何一个）或出现未知臂名；
* `source_voltage = 0`——合法，零输出并标注，不是错误；
* 反解时给了四个臂（没有未知臂可解，目标不自洽）或少于三个臂；
* 已知臂中出现零/负阻值——在除法发生之前拦下，不会冒出 ZeroDivisionError。

## 测试守护的物理关系

`pytest -q` 全部通过，其中与验收直接对应的：

1. **相对臂乘积相等 → 开路输出为零**（含四臂相等基准、非等臂平衡例、
   以及「相邻臂相等并不平衡」的反例）；
2. **固定三臂单调扫动待测臂**，越平衡点时输出符号翻转；
3. **桥源电压翻倍 → 同一失衡程度下输出绝对值翻倍**；
4. **反解闭合**：四个未知臂位置逐一参数化，`/bridge/solve` 解出的臂
   经 `/bridge/output` 正算输出归零；
5. 检流计：`Ig = V_th/(R_th+Rg)`、端电压随加载而减小、平衡时读数为零；
6. 各类非法输入在计算前被挡下并带 reason；两个电桥档阻值相互独立。
