" 道语言配置文件语法高亮（道.配置）
" 字段与 源码/dao/package/config.py 的 PackageConfig 保持一致。

if exists("b:current_syntax")
  finish
endif

syn keyword daoConfigField 道版本 名称 版本 作者 描述 入口
syn keyword daoConfigSection 开发依赖 依赖
syn match daoConfigVersionOperator "\(>=\|<=\|==\|\^\|~\|>\|<\)"
syn match daoConfigVersion "\d\+\.\d\+\.\d\+\([-+][A-Za-z0-9.]\+\)\?"
syn match daoConfigComment "//.*$"

hi def link daoConfigField        Keyword
hi def link daoConfigSection      Include
hi def link daoConfigVersion      Number
hi def link daoConfigVersionOperator Operator
hi def link daoConfigComment      Comment

let b:current_syntax = "daoconfig"
