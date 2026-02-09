#!/usr/bin/env python3
"""
自动修改解释器中所有抛出错误的方法，添加self.source参数
"""

import os
import re

def modify_file(file_path):
    """修改单个文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找到所有抛出错误的地方，如 raise 运行时错误(...)
    pattern = re.compile(r'(raise\s+[\w错误]+)\((.*?)\)', re.DOTALL)
    
    def replace_match(match):
        prefix = match.group(1)
        args = match.group(2).strip()
        
        # 检查是否已经包含source参数
        if ', self.source' in args:
            return match.group(0)
        
        # 检查是否已经有三个参数
        arg_count = len([a for a in args.split(',') if a.strip()])
        
        if arg_count == 1:
            # 只有消息参数：raise 错误("消息")
            return f'{prefix}({args}, 0, 0, self.source)'
        elif arg_count == 2:
            # 消息 + 行号：raise 错误("消息", 10)
            return f'{prefix}({args}, 0, self.source)'
        elif arg_count == 3:
            # 消息 + 行号 + 列号：raise 错误("消息", 10, 5)
            return f'{prefix}({args}, self.source)'
        
        return match.group(0)
    
    new_content = pattern.sub(replace_match, content)
    
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"已修改: {file_path}")
    else:
        print(f"无需修改: {file_path}")

def main():
    """主函数"""
    interpreter_dir = '/home/carson/code/test/道/源码/dao/interpreter'
    
    for filename in os.listdir(interpreter_dir):
        if filename.endswith('.py'):
            file_path = os.path.join(interpreter_dir, filename)
            modify_file(file_path)
    
    print("所有解释器文件修改完成")

if __name__ == "__main__":
    main()