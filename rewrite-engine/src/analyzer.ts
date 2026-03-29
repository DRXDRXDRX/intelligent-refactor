import { ASTManager } from "./astManager";
import { SyntaxKind } from "ts-morph";

/**
 * 代码分析器
 * 负责在指定的 AST 上进行深度的依赖抽取和代码坏味(Code Smell)检测。
 */
export class CodeAnalyzer {
  /**
   * @param astManager 已经初始化并加载了目标项目的 AST 管理器实例
   */
  constructor(private astManager: ASTManager) {}

  /**
   * 构建依赖关系图
   * 遍历给定的文件，提取所有 import 声明，生成文件级的依赖映射表。
   * 
   * @param files 需要分析的文件路径列表
   * @returns 包含各文件对外依赖模块的映射图对象
   */
  public buildDependencyGraph(files: string[]) {
    const graph: Record<string, string[]> = {};
    for (const filePath of files) {
      const sourceFile = this.astManager.getSourceFile(filePath);
      if (!sourceFile) continue;
      
      // 获取当前文件中的所有 import 语句
      const imports = sourceFile.getImportDeclarations();
      // 提取被引入模块的路径或名称 (例如：'react', './utils')
      graph[filePath] = imports.map(imp => imp.getModuleSpecifierValue());
    }
    return { graph };
  }

  /**
   * 检测代码坏味 (Code Smells)
   * 扫描指定文件，发现潜在的可重构点（例如：过长函数、上帝类等）。
   * 目前实现了一个简单的规则：检测超过 20 行的函数。
   * 
   * @param files 需要扫描的文件路径列表
   * @returns 发现的代码坏味告警列表
   */
  public detectCodeSmells(files: string[]) {
    const smells: any[] = [];
    for (const filePath of files) {
      const sourceFile = this.astManager.getSourceFile(filePath);
      if (!sourceFile) continue;

      // 提取文件中的所有普通函数声明
      const functions = sourceFile.getDescendantsOfKind(SyntaxKind.FunctionDeclaration);
      for (const func of functions) {
        // 计算函数体所占的行数
        const lineCount = func.getEndLineNumber() - func.getStartLineNumber();
        
        // 阈值设为 20 行，超过则判定为"长函数"坏味
        if (lineCount > 20) {
          smells.push({
            type: "long_function", // 坏味类型标识
            file: filePath,
            symbol: func.getName(),
            lines: lineCount,
            message: `Function ${func.getName()} is ${lineCount} lines long.`
          });
        }
      }
    }
    return smells;
  }
}