" 道语言文件类型识别
" 把本插件目录加入 runtimepath 后自动生效。
" 识别扩展名：.道（中文扩展名）与 .dao（兼容西文扩展名）。

augroup dao_ftdetect
  autocmd!
  autocmd BufRead,BufNewFile *.道,*.dao set filetype=dao
  autocmd BufRead,BufNewFile 道.配置 set filetype=daoconfig
augroup END
