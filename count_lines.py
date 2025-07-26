#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件行数统计工具
统计指定目录下所有文件的行数
"""

import os
import sys
import argparse
from pathlib import Path

def count_lines_in_file(file_path):
    """统计单个文件的行数"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return len(f.readlines())
    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                return len(f.readlines())
        except:
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return len(f.readlines())
            except:
                return 0
    except Exception as e:
        print(f"⚠️ 无法读取文件 {file_path}: {e}")
        return 0

def is_text_file(file_path):
    """判断是否为文本文件"""
    text_extensions = {
        '.py', '.txt', '.md', '.json', '.xml', '.html', '.htm', '.css', '.js',
        '.java', '.cpp', '.c', '.h', '.hpp', '.cs', '.php', '.rb', '.go',
        '.rs', '.swift', '.kt', '.scala', '.sql', '.sh', '.bat', '.ps1',
        '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.log',
        '.csv', '.tsv', '.tex', '.r', '.m', '.pl', '.lua', '.vim'
    }
    
    return file_path.suffix.lower() in text_extensions

def count_lines_in_directory(directory_path='.', recursive=True):
    """统计目录下所有文件的行数"""
    directory = Path(directory_path)
    
    # 检查目录是否存在
    if not directory.exists():
        print(f"❌ 目录不存在: {directory.absolute()}")
        return 0, 0
    
    if not directory.is_dir():
        print(f"❌ 路径不是目录: {directory.absolute()}")
        return 0, 0
    
    total_lines = 0
    file_count = 0
    results = []
    
    print(f"📁 正在统计目录: {directory.absolute()}")
    print(f"🔍 递归搜索: {'是' if recursive else '否'}")
    print("=" * 60)
    
    # 遍历目录下的所有文件
    if recursive:
        file_iterator = directory.rglob('*')
    else:
        file_iterator = directory.glob('*')
    
    for file_path in file_iterator:
        if file_path.is_file() and is_text_file(file_path):
            lines = count_lines_in_file(file_path)
            if lines > 0:
                relative_path = file_path.relative_to(directory)
                results.append((str(relative_path), lines))
                total_lines += lines
                file_count += 1
    
    # 按行数排序（从多到少）
    results.sort(key=lambda x: x[1], reverse=True)
    
    # 显示结果
    print(f"{'文件名':<50} {'行数':>8}")
    print("-" * 60)
    
    for file_name, lines in results:
        print(f"{file_name:<50} {lines:>8}")
    
    print("=" * 60)
    print(f"📊 统计结果:")
    print(f"   文件总数: {file_count}")
    print(f"   总行数: {total_lines:,}")
    print(f"   平均每文件行数: {total_lines/max(file_count, 1):.1f}")
    
    return total_lines, file_count

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='统计指定目录下所有文件的行数',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python count_lines.py                    # 统计当前目录
  python count_lines.py /path/to/project   # 统计指定目录
  python count_lines.py . --no-recursive   # 只统计当前目录，不递归子目录
  python count_lines.py ../src -r          # 统计上级目录的src文件夹（递归）
        """
    )
    
    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='要统计的目录路径（默认为当前目录）'
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        default=True,
        help='递归搜索子目录（默认开启）'
    )
    
    parser.add_argument(
        '--no-recursive',
        action='store_false',
        dest='recursive',
        help='不递归搜索子目录'
    )
    
    return parser.parse_args()

def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    print("🔍 文件行数统计工具")
    print("=" * 60)
    
    try:
        total_lines, file_count = count_lines_in_directory(args.directory, args.recursive)
        
        if file_count == 0:
            print("❌ 指定目录下没有找到可统计的文本文件")
        else:
            print(f"\n✅ 统计完成！目录下共有 {file_count} 个文件，总计 {total_lines:,} 行代码")
            
    except KeyboardInterrupt:
        print("\n❌ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()