" 道语言传统正则语法高亮
" 说明：道语言暂无 tree-sitter grammar，因此使用 Vim 原生正则高亮。
" 关键字表完整来源于 源码/dao/tokens.py 的 KEYWORDS 字典。
" 共 79 个键（其中「运行异步」在解释器里按内置函数处理，此处一并高亮）。
" 关键字按语义分为多组（声明/流程/条件/循环/模块/函数/类型/布尔/逻辑运算/
" 异常/OOP 修饰符/OOP 结构/并发类型/并发控制/逻辑编程/宏），全部纳入
" @daoInterp cluster 以保证模板字符串插值内同样高亮。

if exists("b:current_syntax")
  finish
endif

" 说明：UTF-8 环境下 'iskeyword' 默认的 @ 已包含汉字（CJK 表意文字属于
" 字母类），因此「如果」「否则如果」等中文关键字可直接作为完整的词匹配，
" 无需（也不能用 iskeyword+=一-龥 这种多字节范围写法）额外设置。
syn case match

" ------------------------------------------------------------------
" 关键字（按语义分组，链到 Vim 标准高亮组；每组长词在前）
" ------------------------------------------------------------------

" 声明
syn keyword daoDeclaration 定义 常量 设 函数
" 流程 / 范围（返回、产出、默认及区间关键字）
syn keyword daoFlow 返回 产出 默认 在 从 到
" 条件分支
syn keyword daoConditional 否则如果 如果 否则 匹配 情况
" 循环
syn keyword daoRepeat 当 遍历 对于 步长 跳出 继续
" 模块
syn keyword daoModule 导入 导出 作为
" 函数与宏定义 / 内置异步运行函数
syn keyword daoFunction 定义宏 运行异步
" 类型声明
syn keyword daoType 类型别名 类型 枚举 特征
" 布尔值与空值
syn keyword daoBoolean 真 假 空
" 逻辑运算符（关键字形式）
syn keyword daoOperatorKeyword 并且 或者 不是 不在 且 非
" 异常处理
syn keyword daoException 尝试 捕获 最终 抛出 断言
" OOP 可见性 / 修饰符
syn keyword daoOopModifier 受保护 私有 静态 抽象
" OOP 结构（继承、构造、this/super、存取器、运算符重载）
syn keyword daoOop 运算符 继承自 初始化 本对象 父对象 实现 获取 设置
" 并发类型（通道、锁、原子量）
syn keyword daoConcurrencyType 原子整数 原子布尔 互斥锁 通道
" 并发控制（异步、组合子、通道操作与同步）
syn keyword daoConcurrency 异步 等待 全部 竞速 并行 发送 接收 选择 超时 同步
" 逻辑编程（逻辑块、事实、规则、查询、剪枝、范围约束）
syn keyword daoLogic 逻辑 事实 规则 查询 剪枝 在范围
" 宏系统（引述、引用、注入）
syn keyword daoMacro 引述 引用 注入

" ------------------------------------------------------------------
" 数值
" ------------------------------------------------------------------
syn match daoNumber /\d[\d_]*\%(\.\d[\d_]*\)\?/

" ------------------------------------------------------------------
" 逻辑变量 ?变量、宏注入 $变量、宏调用 !宏
" ------------------------------------------------------------------
syn match daoLogicVar /?[一-龥A-Za-z_][一-龥A-Za-z_0-9]*/
syn match daoMacroInjection /\$[一-龥A-Za-z_][一-龥A-Za-z_0-9]*/
syn match daoMacroCall /![一-龥A-Za-z_][一-龥A-Za-z_0-9]*/

" ------------------------------------------------------------------
" 注解 @名称（运行时装饰器，锚定行首可缩进，支持中文注解名）
" ------------------------------------------------------------------
syn match daoAnnotation /^\s*\zs@[一-龥A-Za-z_][一-龥A-Za-z_0-9]*/

" ------------------------------------------------------------------
" 运算符与管道（较宽泛的单字符在前，较具体的多字符在后）
" 注：除法 / 不单独高亮，以免与 // 注释、/* 块注释冲突。
" ------------------------------------------------------------------
syn match daoOperator /[+\-*%<>=|]/
syn match daoOperator /\.\./
syn match daoOperator /\.\.\./
syn match daoOperator /|>/ " 管道
syn match daoOperator /=>/
syn match daoOperator /->/
syn match daoOperator /==/
syn match daoOperator /!=/
syn match daoOperator />=/
syn match daoOperator /<=/
syn match daoOperator /\*\*/
syn match daoOperator /&&/
syn match daoOperator /||/

" ------------------------------------------------------------------
" 字符串与转义（西文 / 中文引号，含三引号）
" ------------------------------------------------------------------
syn match daoEscape /\\./
syn region daoString start=/"/ skip=/\\"/ end=/"/ contains=daoEscape
syn region daoString start=/'/ skip=/\\'/ end=/'/ contains=daoEscape
syn region daoString start=/“/ end=/”/ contains=daoEscape
syn region daoString start=/‘/ end=/’/ contains=daoEscape
syn region daoString start=/「/ end=/」/ contains=daoEscape
" 三引号定义在后，优先于单引号
syn region daoString start=/"""/ end=/"""/ contains=daoEscape
syn region daoString start=/'''/ end=/'''/ contains=daoEscape

" ------------------------------------------------------------------
" 模板字符串 `文本 {表达式}`，表达式内复用顶层高亮
" ------------------------------------------------------------------
syn cluster daoInterp contains=daoString,daoNumber,daoLogicVar,daoMacroInjection,daoMacroCall,daoAnnotation,daoOperator,daoDeclaration,daoFlow,daoConditional,daoRepeat,daoModule,daoFunction,daoType,daoBoolean,daoOperatorKeyword,daoException,daoOopModifier,daoOop,daoConcurrencyType,daoConcurrency,daoLogic,daoMacro,daoLineComment,daoDocComment,daoNoteComment,daoBlockComment
syn region daoInterpExpr start=/{/ end=/}/ contained contains=@daoInterp,daoInterpExpr
syn region daoTemplate start=/`/ skip=/\\`/ end=/`/ contains=daoEscape,daoInterpExpr

" ------------------------------------------------------------------
" 注释：//、///、注：、/* */（块注释支持嵌套）
" ------------------------------------------------------------------
syn match daoTodo /\<\(TODO\|FIXME\|NOTE\|XXX\)\>/ contained
" // 后若紧跟 / 则交给文档注释规则处理
syn match daoLineComment /\/\/\%([^/].*\)\?$/ contains=daoTodo
syn match daoDocComment /\/\/\/.*$/ contains=daoTodo
syn match daoNoteComment /注[：:].*$/ contains=daoTodo
syn region daoBlockComment start=/\/\*/ end=/\*\// contains=daoBlockComment,daoTodo fold

" ------------------------------------------------------------------
" 高亮链接
" ------------------------------------------------------------------
hi def link daoDeclaration       Statement
hi def link daoFlow              Statement
hi def link daoConditional       Conditional
hi def link daoRepeat            Repeat
hi def link daoModule            Include
hi def link daoFunction          Function
hi def link daoType              Type
hi def link daoBoolean           Boolean
hi def link daoOperatorKeyword   Operator
hi def link daoException         Exception
hi def link daoOopModifier       StorageClass
hi def link daoOop               Structure
hi def link daoConcurrencyType   Type
hi def link daoConcurrency       Special
hi def link daoLogic             Special
hi def link daoMacro             Macro
hi def link daoNumber           Number
hi def link daoLogicVar         Identifier
hi def link daoMacroInjection   Special
hi def link daoMacroCall        Special
hi def link daoAnnotation       PreProc
hi def link daoOperator         Operator
hi def link daoString           String
hi def link daoEscape           SpecialChar
hi def link daoTemplate         String
hi def link daoInterpExpr       Special
hi def link daoLineComment      Comment
hi def link daoNoteComment      Comment
hi def link daoDocComment       SpecialComment
hi def link daoBlockComment     Comment
hi def link daoTodo             Todo

let b:current_syntax = "dao"
