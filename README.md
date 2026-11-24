# 淘宝用户行为分析（Taobao UserBehavior Analysis）

基于公开淘宝 `UserBehavior` 数据集 10 万行抽样样本的用户行为分析项目，完整链路：
**抽样 → 清洗 → 指标分析 → 报告生成 → SQLite/SQL 对照验证 → pytest 单元测试 → BI 导出 → Power BI 看板**。

## 项目结构

```
data/                                # 数据目录（不入库，见"数据准备"）
work/
  random_data.py                     # 从完整 UserBehavior.csv 分块抽样 → sample_100k.csv
  prepare_data.py                    # 小数据清洗入口（全量读入，含共享常量）
  prepare_big_data.py                # 大数据分块清洗（约 1 亿行友好）
  data_analysis.py                   # 指标计算：漏斗/复购/品类/分层/高价值用户
  generate_reports.py                # 生成 reports/ 下的 Markdown 报告、图表与 dashboard_data.json
  export_for_bi.py                   # 导出 Power BI 星型模型 CSV 至 data/bi/（含 assert 自检）
sql/
  sqlite_import.py                   # 清洗结果导入 SQLite
  taobao_behavior_analysis_sqlite.sql # 16 条分析 SQL（与 Python 端指标口径一一对应）
  run_analysis_sql.py                # 逐条执行 SQL 文件并打印结果
test/                                # pytest 单元测试
reports/                             # 生成的报告产物（Markdown / 图表 / dashboard_data.json / taobao_user_analysis.pbix）
```

## 环境与安装

Python 3.8+，依赖见 `requirements.txt`：

```
pip install -r requirements.txt
```

## 数据准备

`UserBehavior.csv`（约 3.5GB）不随仓库分发，请从公开渠道获取后放到 `data/UserBehavior.csv`，然后依次执行：

```
python work/random_data.py           # 均匀抽样 10 万行 → data/sample_100k.csv
python work/prepare_data.py          # 清洗 → data/cleaned_user_behavior.csv
# 数据量大时改用分块版：python work/prepare_big_data.py [--chunksize 2000000] [--no-sort]
```

- 分析窗口默认 `[2017-11-25, 2017-12-04)`（终点不含），共享常量定义在 `work/prepare_data.py`，可用 `--start_date / --end_date` 调整；
- 时间戳统一转换为 `Asia/Shanghai` 本地时间后再派生 `date / hour / weekday` 字段。

## 运行分析

```
python work/data_analysis.py         # 终端输出核心指标
python work/generate_reports.py      # 生成 reports/ 下的报告、图表与仪表盘数据
python sql/sqlite_import.py          # （可选）清洗结果导入 SQLite
python sql/run_analysis_sql.py       # （可选）执行全部 SQL，与 Python 端指标对照
python work/export_for_bi.py         # （可选）导出 Power BI 星型模型 CSV 至 data/bi/
python -m pytest test                # 单元测试
```

## Power BI 看板

BI 层将清洗结果导出为星型模型 CSV（`work/export_for_bi.py`），并在 Power BI Desktop 中建模为三页交互看板（`reports/taobao_user_analysis.pbix`）。

### 链路总览

```
prepare_data.py ──→ data/cleaned_user_behavior.csv
                          │
              export_for_bi.py（含 assert 自检）
                          │
              data/bi/ 5 张 CSV（星型模型导出）
                          │
              Power BI Desktop（reports/taobao_user_analysis.pbix）
                          │
              发布 → Power BI Service
```

### 导出层

| 表 | 类型 | 行数 | 用途 |
|---|---|---|---|
| `fact_user_behavior.csv` | 事实表 | 99,918 | 明细瘦身：user/item/category/behavior/time/date/hour |
| `dim_date.csv` | 日期维度 | 9 | date / weekday / weekday_no / is_weekend |
| `dim_behavior.csv` | 行为维度 | 4 | 行为中英文名与漏斗顺序 sort_order |
| `agg_strict_funnel.csv` | 预聚合 | 13 | 用户-商品级顺序漏斗指标（长表 metric_name / metric_value） |
| `agg_user_value.csv` | 预聚合 | 1,945 | 全部购买用户的 value_score 明细 |

- 编码统一 `utf-8-sig`（Windows 下的 Power Query 读中文列名不乱码）；
- 脚本自带 4 组 assert 自检：事实表行数与清洗数据一致、日期维度覆盖分析窗口、漏斗比率 ∈ [0,1]、行为维度完整性。**任何断言失败说明口径被改动，先修再导**。

### 数据模型

- 星型关系（全链路命脉；缺失的典型症状：**切片器同步正常，但所有数值不随筛选变化**）：
  - `dim_date[date] 1 ─→ * fact_user_behavior[date]`
  - `dim_behavior[behavior_type] 1 ─→ * fact_user_behavior[behavior_type]`
  - 均为一对多、单向筛选（dim → fact）；
- 预聚合表 `agg_strict_funnel`、`agg_user_value` **刻意不与 fact 建关系**：它们是 Python 端物化的单一事实源（口径与权重仅在 `work/data_analysis.py` 定义一次），建关系会让日期切片器切出误导性子集；
- 模型约定：`dim_date` 已标记为日期表；`behavior_name_cn` 按 `sort_order` 排序；fact 的 `date` 隐藏（时间轴统一走 dim_date）；Power Query 已关闭"自动日期/时间"。

### DAX 度量值字典

| 度量值 | 定义要点 | 口径 | 基准值 |
|---|---|---|---|
| 总行为次数 | COUNTROWS(fact) | 全部行为 | 99,918 |
| UV | DISTINCTCOUNT(user_id) | — | 89,224 |
| PV / 收藏 / 加购 / 购买次数 | CALCULATE 按行为类型过滤 | — | 89,596 / 2,849 / 5,515 / 1,958 |
| 浏览过的用户数 | pv 用户去重 | 用户级 | 80,603 |
| 浏览且收藏 / 加购 / 购买用户数 | FILTER(VALUES(user_id)) 行为交集，且要求浏览过 | 用户级 | 451 / 808 / 272 |
| 用户级浏览购买转化率 | DIVIDE（浏览且购买 ÷ 浏览过） | 用户级宽松口径 | 0.34% |
| 复购率 | 购买 ≥ 2 次用户 ÷ 购买用户 | — | 0.67% |
| 加购未购买用户数 | cart > 0 且 buy = 0 | 再营销人群 | 5,406 |
| 顺序漏斗_* | 从 `agg_strict_funnel` 长表按 metric_name 取值 | 用户-商品级，严格时序 | pv_to_buy_pairs = 9，pv_to_buy_pair_rate = 0.01% |

> 基准值已与 `python sql/run_analysis_sql.py` 的 16 项查询及 Python 端报告交叉核对一致；看板搭建或迁移后应逐项重验。

### 看板页面

- **01 经营总览**：KPI 卡片行（总量 / UV / 购买 / 用户级转化率 / 复购率）、DAU + 购买双轴趋势、行为分布图；日期 + 行为切片器；
- **02 转化漏斗**：用户级漏斗卡片墙（含各步转化率）、严格顺序漏斗矩阵、双口径对比说明、加购未购买人群明细表（度量值 `加购未购买标记` + 视觉级筛选实现）；
- **03 品类与用户**：Top10 品类（TopN 筛选）、品类转化明细（PV ≥ 30 防小样本失真）、用户价值分布、Top20 高价值用户表；编辑交互将"品类主题"与"用户主题"的联动隔离。

### 已知口径细节

- **空白 ≠ 0**：计数度量值以 `+0` 显示 0；转化率保留空白——分母为 0 的品类是"无从转化"，不是"零转化"，语义不可混用；
- **value_score 量程 9~22**：底分 = 5+2+1+1（任何购买者的最小组合），权重定义在 `work/data_analysis.py`；数据中无 20 分用户、19 分 4 人并列，Top20 边界用 `价值排名` 计算列（RANKX + user_id 微偏移破并列）保证确定性；
- **预聚合视觉对象不随日期切片联动**：严格漏斗矩阵、价值分布、Top20 表为全窗口口径（页面注释已说明），这是设计特性而非缺陷；
- **品类明细表 PV ≥ 30**：与 Python 端 `category_conversion_analysis` 的防小样本口径对齐；
- **日期切片器三页同步**：同步切片器面板需同时勾选"同步"与"显示"两列。

### 刷新与发布

1. 数据或口径变更后依次执行：`python work/prepare_data.py` → `python work/export_for_bi.py`（assert 自动把关）→ Power BI"主页 → 刷新"；
2. 数据源建议用"**文件夹**"方式指向 `data/bi/`，新增表无需改连接；
3. 发布：主页 → 发布 → 个人工作区（免费版即可）；本地 CSV 的计划刷新需配置本地数据网关（个人模式），演示项目用手动刷新即可；
4. pbix 内数据源为本地绝对路径，换机器需重连数据源。

### 快速复现

```
1. pip install -r requirements.txt
2. python work/random_data.py && python work/prepare_data.py
3. python work/export_for_bi.py
4. 用 Power BI Desktop 打开 reports/taobao_user_analysis.pbix
5. 提示重连数据源时指向 data/bi/ 文件夹
6. 对照"DAX 度量值字典"逐项核对基准值
```

## 分析口径说明

- **两套转化漏斗**：用户级漏斗（不限商品、不限顺序，看人群整体转化）与用户-商品级顺序漏斗（要求同一商品且后序行为晚于前序，评估真实购买路径）。Python 端与 SQL 端两套口径已对齐，数值可直接互验；
- **用户价值评分（value_score）**：经验权重（购买次数 × 5 + 购买商品数 × 2 + 购买品类数 × 1 + 活跃天数 × 1），属启发式设置，可按运营目标调整；
- **样本量提示**：10 万行样本中购买用户约 2000 人，复购率等比率类指标置信区间较宽，业务结论需结合样本量谨慎解读。
