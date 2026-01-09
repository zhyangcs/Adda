# Adda Demo App（Short Paper 演示系统）— 面向会议参与者的 UI/UX 与展示逻辑说明

本文档面向**会议参与者**，目标是帮助观众在有限时间内理解这个 demo：

- **展示了什么**（系统功能特性与可视化内容）
- **如何交互**（UI/UX 设计与典型操作）
- **为何这样设计**（它如何把 Adda AutoFE 的研究亮点“讲清楚、看得见”）

说明：本文刻意**不**展开端口、启动方式、接口细节等实现层内容；只在必要时用“后台服务 / 数据接口 / WebSocket 推送”等抽象术语描述数据如何进入 UI。

---

### 1. Demo 讲述的“研究故事线”（What to watch for）

这个 demo 用一个非常明确的三段式叙事，把 Adda 的核心研究思想变成“可以被观看和操作”的体验：

- **(A) Agent-driven Feature Generation**：把“自动特征工程的搜索过程”从黑盒变成可观察的过程（Agent 协作 + 生成树）。
- **(B) In-Database Feature Computation**：把“把 Python pipeline 映射为可在数据库执行的计算图”可视化（DAG + Python/SQL/UDF 对照 + AST 下钻）。
- **(C) Performance**：把“研究效果”以可对比的方式呈现（性能、时间、解释性/重要性），并与其他方法做对比。

这三个页面不是孤立的 UI：它们对应研究系统的三类关键证据：

- **过程证据**：Adda 如何生成特征、如何验证/选择（A）。
- **可落地证据**：为什么能在 DB 内执行，哪些能转 SQL，哪些需要 UDF（B）。
- **结果证据**：效果、效率、可解释性与对比（C）。

---

### 2. 全局 UI/UX 设计（整体布局与交互原则）

#### 2.1 “三段式 Workflow + 参数侧栏 + 主画布”的整体布局

整个应用采用统一壳层（MainLayout）：

- **顶部导航（TopNavigation）**：三段式 workflow 切换（Agent / In-DB / Performance），并在右侧提供**与当前页面语义一致的主动作按钮**。
- **左侧栏（Task Configuration，可折叠）**：集中放置“演示参数”（任务描述、数据集、Agent 模型、下游 ML 模型；在 Performance 页额外提供对比方法选择）。
- **中间主区域（router-view）**：显示当前 workflow 的核心可视化与讲述内容。
- **底部浮层控制条（ExecutionControlBar，可折叠）**：提供“第二条控制通道”，用于某些页面的 step-wise 演示（例如 Agent 页的 Next Step）。

这样的布局对会议演示特别友好：

- 观众始终知道“我在哪个阶段”（顶部三段式按钮）。
- 主画布始终保持最大面积（左侧栏可折叠）。
- 参数修改不会打断观看（集中在左侧）。
- 演示者始终有一个“随手可点的主按钮”（顶部右侧），并在需要时用底部控制条做更细粒度控制（例如逐步推进）。

#### 2.2 左侧 Task Configuration：把“演示参数”收口，降低观众负担

左侧栏的 UI 设计目标是“观众只需要知道三件事”：

- **做什么任务（Task Description）**：一句话的问题定义，帮助观众把后续的特征与指标对上业务语义。
- **用什么数据（Dataset）**：提供一组可快速演示的数据集选项。
- **用什么模型（Agent Model / Downstream ML Model）**：把“LLM 负责生成”和“DB/ML 负责训练评估”这两层概念明确区分。

在 Performance 页额外提供：

- **Comparison Methods**：Adda 默认包含且不可取消，观众可以勾选额外 baselines（例如 AutoFeat / MADlib / CAAFE），用于对比展示。

左侧栏底部还有**状态指示**（Ready/Initializing/Running/Completed/Error + processing 动画），面向会议演示的意义是：演示者可以用它解释“系统当前在忙什么”，避免观众误以为卡住或无响应。

#### 2.3 顶部导航的“主动作按钮”：让每个 workflow 都有一个明确的入口

顶部导航右侧按钮的语义随页面变化：

- **Agent-driven Feature Generation**：Run / Pause / Resume / Clear / Stop（对“可暂停/可恢复的特征搜索”进行节奏控制）。
- **In-Database Feature Computation**：Run（触发刷新/重新拉取可视化所需数据；具体表现取决于后台是否有新结果）。
- **Performance**：Run（触发端到端流程的执行或刷新结果）。

这种“单一主动作”的设计非常适合投屏：演示者不需要在复杂菜单里找入口，观众也能形成稳定预期。

#### 2.4 底部浮层控制条：为演示节奏提供“第二操控杆”

底部控制条是一个可折叠的浮层：

- 默认贴近屏幕下边缘，半透明卡片，避免遮挡主画布。
- 折叠后只保留一个小型 “Control” pill，点击即可展开。

它在不同页面提供不同能力：

- **Performance 页**：Start / End&Clear（强调“一键跑通”和“一键收尾清理”）。
- **Agent 页**：Next Step / Show Agent Thinking（强调“逐步推进 + 讲解辅助”）。

#### 2.5 设计原则：把“动态过程”变成“可读的动画与结构”

与常见 AutoFE demo 不同，本系统强调：

- **让观众看到搜索在发生**（工作中的 Agent 高亮、连接箭头动效、思考流不断滚动）。
- **让观众看到结构在生长**（Feature Tree 的层级扩展、节点验证状态、节点信息面板联动）。
- **让观众看到可执行性**（Python/SQL/UDF 对照、DAG tooltip、AST 预览/下钻）。

---

### 3. 页面 A：Agent-driven Feature Generation（过程可视化）

对应文件：`autofe-frontend/src/components/Layout/Content/MainContent.vue`

#### 3.1 页面布局：左右分栏（Split Panes）+ “可折叠的讲解辅助面板”

- **左侧主区域**（信息密度最高）：
  - **Agent Thinking Process**：4 个 Agent 的协作可视化（System / Main Agent / Opt Agent / Node Validation），并用“工作中”动效强调当前活跃角色。
  - **Feature Generation**：特征生成树（Feature Tree，D3 可视化），承载“搜索空间 / 生成过程”的核心证据。
  - **Node Information**：当前选中节点的细节（用于解释节点语义、操作类型与验证分数）。
- **右侧面板**：
  - **Agent Thinking Feed**：实时思考消息流（面向“过程解释/可讲述”）。支持把消息拆成**文本 / 代码块 / 示例列表**，并以折叠块呈现长内容。

右侧面板可折叠（投屏常用）：

- 支持通过 splitter 点击、快捷键（例如 `Ctrl + ←/→` 与 `Esc`）快速折叠/展开。
- 折叠状态与左右比例会被记忆（本地保存用户偏好），方便连续多次演示。

#### 3.2 关键交互（两种演示方式）：Continuous Feature Search vs. Step-wise Next Step

该页面刻意提供两种“可讲述的操控方式”，适配不同的会议时间与讲解风格：

**A) Continuous Feature Search（顶部导航右侧按钮）**：适合做“动态过程”叙事

- **Run**：启动可暂停/可恢复的特征搜索；观众会看到 Agent 状态与树结构持续更新。
- **Pause / Resume**：演示“人可以介入节奏”，便于你停下来讲清某个节点或某条思考信息。
- **Stop**：中止搜索（用于“控制时间”或“快速切换到下一段”）。
- **Clear**：清空已展示的输出（树、agent 状态缓存、thinking feed），为下一次演示做准备。

**B) Step-wise Next Step（底部浮层控制条）**：适合做“可控的逐步讲解”

- **Next Step**：每次只推进一步，适合在投屏时逐步解释“这一步系统做了什么”。
- **Show Agent Thinking**：作为讲解辅助，强调“系统不是盲目生成”，而是有可读的 reasoning 轨迹。

#### 3.3 Feature Tree：把“搜索空间”具象化为树

Feature Tree 的 UX 目标是：

- 让观众看到：特征是如何从根节点逐步扩展/组合出来的；
- 让观众理解：每个节点不是“随便的表达式”，而是与某个 operation、代码片段、验证分数相关联。

观众可见的关键操作：

- **点击节点**：节点卡片高亮（浅绿色背景 + 绿色边框），Node Information 同步更新。
- **缩放/拖拽**：支持滚轮缩放与拖拽平移，适合投屏时在“全局结构”和“局部细节”之间切换。
- **自适应缩放**：系统会根据树深度计算初始缩放比例（例如 3 层树会做更大放大），保证一上来就“看得清”。
- **验证状态可视化**：当节点分数尚未可用时，节点会显示类似 “Score: validating”，强调“系统在验证而不是凭空给分”。

#### 3.4 Node Information：把“树节点”解释给观众听

该面板承担“讲解者的提词器”角色：

- Node ID、Feature Name、Operation、Description、Score 等字段，让观众把“节点是什么”与“节点为什么被保留”联系起来。
- Python code 折叠块用于把抽象操作落到可理解的代码层（但不强迫观众阅读全部代码）。

#### 3.5 Agent Thinking Feed：把黑盒变成“可讲述的过程”

右侧思考流的 UX 重点：

- 自动滚动。
- 分段解析（文本、代码块、示例列表）并用 `<details>` 折叠，避免长消息挤爆画面。
- 消息按 Agent 做视觉区分（头像/背景色），帮助观众建立“谁在做什么”的心智模型。

会议展示建议：

- 用 2–3 条思考消息解释“系统在考虑什么、为什么要生成这些候选特征”，再切回树与节点信息展示“结果落到哪”。

#### 3.6 额外 UX：投屏友好（快速聚焦主画布）

为投屏/讲解服务的设计：

- 支持一键折叠右侧 thinking 面板（让树与节点信息占满屏幕）。
- 支持快捷键与 splitter 点击切换（演示时不依赖精确拖拽）。
- 滚动条默认隐藏，交互时才出现，减少“视觉噪音”。

---

### 4. 页面 B：In-Database Feature Computation（可执行性可视化）

对应文件：`autofe-frontend/src/components/Layout/Content/InDatabaseContent.vue`

该页面的任务不是再“生成特征”，而是解释研究贡献中的关键落地能力：

- **哪些 pipeline 逻辑可以转 SQL 并 pushdown 到数据库执行？**
- **哪些步骤需要 UDF，为什么？**
- **整个 pipeline 在数据库视角是什么计算图？**

#### 4.1 Final SQL（最终可执行物）

页面上方首先给出 “Final SQL” 卡片（当后台可提供 SQL 时）：

- **状态 badge**：区分“实时生成”与“已存在”（对应 demo 里两种常见情形：刚跑完 pipeline vs. 复用已有产物）。
- **copy action**：复制 SQL 或复制 SQL 位置（用于演示“结果可带走”，也便于后续论文/报告整理）。
- **warning 区域**：若 SQL 生成过程中存在警告，会显式提示；对会议演示的意义是“诚实展示边界”。

#### 4.2 Pipeline DAG（高层结构）+ Hover Tooltip（低层细节）

UI/UX 设计成“先宏观、后细节”：

- 先给出**DAG 视图**（节点与边，展示执行顺序与依赖）。
- 再通过 **hover tooltip** 展示节点细节（Python / SQL / UDF），避免页面上同时铺满大量代码导致观众失焦。

该 DAG 的视觉编码对演示很关键：

- **Start / End 节点**：使用数据库/表格图标，让观众一眼理解“从数据到结果”的边界。
- **普通算子节点**：使用蓝色 header（表示可映射/可下推的 operator）。
- **UDF/不支持节点**：使用橙色 header，并带 Python 图标提示“此处需要 UDF（py2sql fallback）”。

tooltip 的交互也为投屏做了优化：

- tooltip 位置**锚定在节点附近**（不是跟随鼠标），避免投屏时抖动。
- tooltip 与节点之间保留轻微重叠区，减少从节点移动到 tooltip 的“闪烁”。

会议展示建议：

- 先指着 DAG 解释“这是从 pipeline 到数据库执行图的映射”；
- 再选 1–2 个节点 hover 展示：
  - 可转 SQL 的节点：强调 pushdown；
  - UDF 节点：强调边界与工程策略（而不是“全都转 SQL”）。

#### 4.3 Step-by-step Block（逐段解释）+ 语义摘要 + AST 预览/下钻

该区域是“把一个 pipeline step 说清楚”的工具，并用“语义摘要”降低观众的理解成本：

- **分页**：一次只展示一个 step（“Step i · Node j”），适合会议讲解节奏。
- **Semantic summary 卡片**：先用 Inputs / Operator / Outputs 的布局建立“这个 step 在做什么”。
  - 用 chip 标出 **Operator** vs **UDF (Python)**。
  - 用 chip 标出 **SQL convertible** vs **Requires UDF / not convertible**。
  - 参数摘要会在 operator 卡片中显示（例如“参数: …”）。
- **AST preview / raw AST drill-down**：
  - 默认可展示 AST 预览（较浅层的 AST）。
  - 也支持下钻完整 AST（给对程序分析更感兴趣的观众）。
- **Python Monaco viewer**：右侧代码用 editor 风格展示（只读），更像“可执行工件”，而不是静态截图。

#### 4.4 这页在研究展示中的角色（讲解要点）

该页并不是在展示“SQL 写得多漂亮”，而是在展示**研究贡献中的落地性**：

- **pushdown 能力**：哪些步骤能下推，哪些不能（并不回避边界）。
- **可解释的编译过程**：从 Python pipeline 到 SQL/UDF 的映射是“可被观看、可被复述”的。
- **可证据化的工程策略**：UDF 不是妥协，而是边界条件下的可行路径。

---

### 5. 页面 C：Performance（结果证据：性能 / 时间 / 解释性）

对应文件：`autofe-frontend/src/components/Layout/Content/EndToEndContent.vue`

该页面把研究结果打包成 2×2 的“结论面板”（四个子面板），专门为投屏做了排布与视觉层次：

- **Performance Comparison**：效果对比（AUC / F1）。
- **Time Comparison**：效率对比（Training + End-to-End Latency）。
- **Feature Explainability**：解释性/重要性（Top-7 + SHAP/IG/FI；其中 Top-7 是 paper view）。
- **RFE Feature Importance**：RFE 视角的重要性排序（列表式，易读）。

页面还提供“面向会议的运行反馈”：

- 运行时可显示遮罩层（进度条 + 阶段性文案），强调“系统正在执行端到端流程”。
- 执行成功后会弹出右上角成功通知（短暂出现，避免遮挡）。

#### 5.1 Performance Comparison（AUC / F1）

UX 设计要点：

- 指标切换（AUC vs F1）用 tab/toggle，避免下拉框引发额外注意力。
- hover tooltip 给出 rank 与数值，适合演示时“点名比较”。
- HD 导出按钮支持快速产出高质量图（内置白底，并做高清缩放），便于论文/报告配图。
- 柱状图按分数排序，观众可直接读出“谁最好、Adda 排第几”。

#### 5.2 Time Comparison（Latency / Training）

UX 设计要点：

- seconds/minutes 切换，适配不同数据集量级（观众更容易理解“分钟级 vs 秒级”）。
- 同时展示 **Training Time** 与 **End-to-End Latency**（两条 bar），让观众区分“训练成本”和“端到端成本”。
- Adda 会用虚线框在图中被强调，帮助观众在多方法对比中快速定位。

#### 5.3 Feature Explainability（Top-7 + 多方法重要性）

这是最贴近“short paper 讲述”的解释性面板：

- **Top-7（paper view）**：把复杂的重要性分析压缩成“Top-K 中 Generated（NEW）特征的占比 + 具体特征列表”。
  - 每个方法一张卡片：显示百分比、Generated/Top-K 计数、Top-K 特征列表（带 NEW/Original badge），并用迷你柱形强调相对重要性。
  - 这能非常直接地回答观众关键问题：**Adda 的提升是否来自“真正有用的新特征”？**
- **SHAP / IG / FI 视图**：为更技术的观众提供多视角证据（不同重要性定义的对照）。
  - 下方提供 Feature Rankings 列表：排名徽章 + 归一化条形 + 数值（必要时显示“缩放倍数 ×k”，说明为了可视化做了 scale）。
- **Fullscreen**：允许把解释性面板铺满屏幕，便于在投屏时读长特征名/读排名细节。

会议展示建议：

- 先用 Top-7 讲一个“强叙事句”：Adda 生成的新特征在 top-k 中占比更高/更集中；
- 再切到 SHAP 或 IG/FI，用 1–2 个特征名作为例子，让观众看到“哪些特征被认为重要”。

#### 5.4 RFE Feature Importance（列表式、投屏友好）

RFE 面板刻意采用“列表 + 条形”的极简表达：

- 默认展示 Top-N（例如前 15 个）最重要特征。
- 对生成特征打 NEW 标记，形成“新特征贡献”的直观证据。
- 鼠标悬停可查看完整特征名（长特征名在投屏中通常会被截断）。

---

### 6. Snapshot 页面（为“论文配图/截图”服务）

系统包含两类“无 chrome”页面（不显示顶部导航与左侧栏），用于生成干净图像（MainLayout 支持 hideChrome）：

- `Feature Importance Snapshot`
- `Performance Snapshot`

它们的 UI 设计侧重点是：

- 去掉操作干扰元素；
- 保持图表在截图尺寸下可读；
- 为 Top-7 卡片宽度、布局等提供微调空间（更适合 paper figure 的排版要求）。

补充说明（对论文写作很关键）：

- Snapshot 页面往往会提供“横版/竖版”两种图表构型（例如同一组结果同时给出 vertical/horizontal 的柱状对比），方便匹配不同版式。
- Snapshot 的控件区会收口为最小必要参数（数据集、下游模型、对比方法），而不会暴露整个系统的配置面板。

---

### 7. 会议演示建议：一条 6–8 分钟的顺滑路径

你可以按以下顺序演示（每一步都对应一个“研究观点”）：

- **(1) 配置任务（左侧栏）**：说明数据集与下游模型（为后面指标解释做铺垫）。
- **(2) 进入 Agent-driven Feature Generation**：
  - 点击 Run → 让观众看到“系统开始工作”（Agent 高亮、树开始扩展、thinking feed 出现）
  - 解释 Agent 协作图 → 说明角色分工（System/Main/Opt/Validation）
  - 点击树节点 → 用 Node Information 讲 1 个节点的含义与分数/验证状态
  - 右侧 thinking feed 选 1 条讲“为什么生成/验证”
  - 若需要更强可控性：用底部 Next Step 逐步推进，边走边讲
- **(3) 切到 In-Database Feature Computation**：
  - 先看 Final SQL（强调“最终可执行物可复制/可带走”）
  - 再看 DAG（宏观结构）
  - hover 一个可转 SQL 的节点 + 一个 UDF 节点（强调 pushdown 与边界）
  - 分页展示 1 个 block 的语义摘要 + AST 预览（点到为止）
- **(4) 切到 Performance**：
  - AUC/F1 对比 → 讲“有效性”
  - Time 对比 → 讲“效率/端到端代价”
  - Top-7 解释性 → 讲“新特征贡献”

可选的“更短版本”（约 3 分钟）：

- 直接从 Agent 页 Run 开始，停 15–20 秒让树长出 2–3 层 → 点一个节点讲清楚。
- 立刻切到 Performance 页，展示 AUC + Time + Top-7 三张图给出结论。

---

### 8. 这套 UI/UX 如何服务 Adda AutoFE 的研究展示（总结）

从“研究展示”角度，这套 demo 的 UI/UX 做了三件关键事情：

- **把黑盒过程变成可观察过程**：Agent 状态 + thinking feed + feature tree 的联动，让观众相信“系统确实在做系统性搜索与验证”。
- **把可执行性变成可视化证据**：DAG + Python/SQL/UDF 对照，让观众理解“为什么能在数据库内运行、哪里需要 UDF”。
- **把结论变成可对比、可解释的图表**：Performance/Time/Top-7 解释性让观众快速得到结论，并理解结论来自哪里。

---

### 9. 讲解者备忘（Speaker Notes：高频问题与对应 UI 证据）

#### 9.1 “这不是黑盒吗？你怎么证明它在‘系统性搜索’？”

可指向的 UI 证据：

- **Agent Thinking Process** 的活跃高亮与箭头动效（谁在工作一目了然）。
- **Thinking Feed** 的可读消息（文本 + 代码 + 示例列表），可以摘 1 条“生成候选 + 给出理由”的消息。
- **Feature Tree** 的结构生长 + 节点验证状态（Score validating → score 成型）。

#### 9.2 “你说能 pushdown 到 DB，哪里能看出来？”

可指向的 UI 证据：

- In-DB 页的 **DAG 节点颜色/图标编码**：operator vs UDF。
- **tooltip** 里的 Python/SQL/UDF 三段对照（把映射讲清楚）。
- **Final SQL** 卡片（最终可执行物）。

#### 9.3 “Adda 的提升来自什么？是不是只是跑得久？”

可指向的 UI 证据：

- **Time Comparison**：把 Training 与 End-to-End 分开展示，避免“把全部时间混成一个数”。
- **Top-7（paper view）**：展示 NEW 特征在 Top-K 中的占比与具体名字，回答“提升来自哪些新特征”。
- **SHAP/IG/FI 排名**：用不同重要性定义交叉验证“哪些特征重要”。

---

### 10. 术语小词典（用于观众提问时快速对齐）

- **Node / Feature Node**：Feature Tree 里的一个节点，代表一个候选特征（含操作类型、代码片段与验证分数）。
- **Operation / Operator**：对特征的变换操作（可能可映射为 SQL）。
- **Validation**：对候选特征的有效性评估/打分过程（因此会出现 “validating” 状态）。
- **Pipeline**：从原始数据到可训练输入的一串变换步骤。
- **DAG**：Pipeline 的依赖结构表达（用于解释执行顺序与可下推范围）。
- **Pushdown**：把可执行的变换从应用层下推到数据库执行。
- **UDF**：当某些操作无法直接翻译为 SQL 时，在数据库内以用户自定义函数执行的路径。
- **Top-K / Top-7**：论文视图中的简化指标：在最重要的 K 个特征里，生成特征（NEW）的占比与列表。

