import { ASTManager } from "./astManager";
import { SyntaxKind } from "ts-morph";

/**
 * 重构执行器 (Refactor Executor)
 * 核心引擎组件：负责接收已解析语义目标的 RefactorIR 指令集，
 * 并利用 ts-morph 的 API 对底层 AST 树进行确定性的增删改操作，最后将结果落盘。
 */
export class RefactorExecutor {
  /**
   * @param astManager 已经初始化并加载了目标项目的 AST 管理器实例
   */
  constructor(private astManager: ASTManager) {}

  /**
   * 按照顺序执行重构指令集
   * 
   * @param instructions 经过 SemanticResolver 校验和定位后的 RefactorIR 列表
   * @returns 成功修改并保存的文件路径列表
   */
  public execute(instructions: any[]) {
    // 使用 Set 记录本次操作中被修改过的文件路径，以便去重
    const modifiedFiles = new Set<string>();

    // 遍历执行每一个重构动作
    for (const ir of instructions) {
      
      // ----------------------------------------------------
      // 动作分支：提取函数 (Extract Function)
      // ----------------------------------------------------
      if (ir.action === "extract_function") {
        const { file, symbol_name } = ir.target;
        // 获取新函数名称及要提取的代码块行号范围
        const { new_function_name, extraction_points } = ir.parameters;
        
        // 1. 定位到目标文件
        const sourceFile = this.astManager.getSourceFile(file);
        if (!sourceFile) continue;

        // 2. 定位到目标原函数
        const targetFunc = sourceFile.getFunction(symbol_name);
        if (!targetFunc) continue;

        // 注意：生产级(Robust)的提取函数逻辑非常复杂（需处理局部作用域变量提升、闭包、返回值等）。
        // 这里提供的是一个 MVP(最小可行性产品) 版本的朴素实现，仅用于演示工作流流转。
        const point = extraction_points[0];
        
        // 3. 收集目标函数体内所有的 Statement（语句）节点
        const statements = targetFunc.getStatements();
        
        // 4. 根据指令传入的 start_line 和 end_line，过滤出需要被提取的语句
        const extractedStatements = statements.filter(stmt => {
           const start = stmt.getStartLineNumber();
           const end = stmt.getEndLineNumber();
           return start >= point.start_line && end <= point.end_line;
        });

        if (extractedStatements.length > 0) {
            // 获取被提取代码的原始文本
            const extractedText = extractedStatements.map(s => s.getText()).join("\n");
            
            // 5. 从原函数 AST 中移除这些被提取的语句节点
            extractedStatements.forEach(s => s.remove());
            
            // 6. 在原函数体内部插入对新函数的调用
            // （为简化演示，这里直接强制插入到函数体索引为 0 的位置，生产环境应计算准确的替换位点）
            targetFunc.insertStatements(0, `${new_function_name}();`);
            
            // 7. 在当前文件 AST 的顶层域，追加生成刚才提取出来的新函数
            sourceFile.addFunction({
                name: new_function_name,
                statements: extractedText
            });

            // 记录该文件发生了变更
            modifiedFiles.add(sourceFile.getFilePath());
        }
      }
      
      // ----------------------------------------------------
      // TODO: 未来可在此扩展更多的动作分支
      // 例如：rename_symbol, inline_variable, move_module 等
      // ----------------------------------------------------
    }

    // 8. 批量将内存中发生的 AST 修改同步写入到底层物理文件系统中
    this.astManager.getProject().saveSync();
    
    // 返回被修改文件的列表，供外层 Validator 及 Git 管理器做进一步校验和 commit
    return { modified_files: Array.from(modifiedFiles) };
  }
}