import { Project, SyntaxKind, Node } from "ts-morph";
import * as fs from "fs";
import * as path from "path";

/**
 * AST 管理器 (基于 ts-morph)
 * 封装了对整个项目的抽象语法树(AST)的加载、解析和基础信息提取能力。
 */
export class ASTManager {
  private project: Project;

  /**
   * 初始化 AST 管理器并加载项目代码
   * @param projectPath 目标沙箱项目的绝对路径
   */
  constructor(projectPath: string) {
    // 检查项目根目录下是否存在 tsconfig.json 文件
    const tsConfigFilePath = path.join(projectPath, "tsconfig.json");
    if (fs.existsSync(tsConfigFilePath)) {
      // 如果存在，则直接通过 tsconfig.json 初始化 ts-morph Project，这样会自动推断类型和项目结构
      this.project = new Project({ tsConfigFilePath });
    } else {
      // 如果不存在（如纯 JS 项目或零散文件），则初始化一个默认的 Project
      // 开启 allowJs 选项以支持 JavaScript 文件
      this.project = new Project({ compilerOptions: { allowJs: true } });
      // 通过 glob 模式主动添加目标目录下的所有 ts/tsx/js/jsx 源代码文件
      this.project.addSourceFilesAtPaths(path.join(projectPath, "**/*.{ts,tsx,js,jsx}"));
    }
  }

  /**
   * 获取底层 ts-morph Project 实例
   * 供其他重写引擎模块（如 Analyzer 和 Executor）调用高级 AST 操作 API
   */
  public getProject() {
    return this.project;
  }

  /**
   * 扫描并返回项目中的所有文件路径
   * 可扩展用于启发式检测当前项目所使用的框架（如检查 package.json 发现 React、Vue 等）
   */
  public scanProject() {
    const files = this.project.getSourceFiles().map(f => f.getFilePath());
    return { files, framework: "Unknown" }; // 框架检测功能在此暂为占位
  }

  /**
   * 对指定的源码文件列表进行基础的 AST 统计分析
   * @param files 需要分析的文件路径数组（绝对或相对路径）
   * @returns 包含各文件函数数量、类数量以及函数特征（名称、行数、参数数）的统计数据对象
   */
  public analyzeAst(files: string[]) {
    const stats: any = {};
    for (const filePath of files) {
      // 尝试获取指定路径对应的 SourceFile AST 根节点
      const sourceFile = this.project.getSourceFile(filePath);
      if (!sourceFile) continue;
      
      // 提取文件中的所有普通函数声明节点
      const functions = sourceFile.getDescendantsOfKind(SyntaxKind.FunctionDeclaration);
      // 提取文件中的所有类声明节点
      const classes = sourceFile.getDescendantsOfKind(SyntaxKind.ClassDeclaration);
      
      // 收集并组装当前文件的统计元数据
      stats[filePath] = {
        functionCount: functions.length,
        classCount: classes.length,
        functions: functions.map(f => ({
          name: f.getName(), // 函数名
          lines: f.getEndLineNumber() - f.getStartLineNumber(), // 计算函数体跨越的代码行数
          parametersCount: f.getParameters().length // 函数定义的参数个数
        }))
      };
    }
    return { ast_stats: stats };
  }

  /**
   * 根据给定的文件路径片段查找并返回完整的 SourceFile 对象
   * @param filePath 可以是相对于项目根目录的相对路径
   * @returns 匹配的 ts-morph SourceFile 实例，未找到则返回 undefined
   */
  public getSourceFile(filePath: string) {
      // 由于 ts-morph 内部维护的都是绝对路径，这里通过路径后缀(endsWith)进行模糊匹配查找
      return this.project.getSourceFile(f => f.getFilePath().endsWith(filePath));
  }
}