import { ASTManager } from "./astManager";
import { SyntaxKind, Node } from "ts-morph";

/**
 * 语义解析器 (Semantic Resolver)
 * 核心职责：解决大模型(LLM)生成的模糊位置与 AST 引擎所需精确位置之间的鸿沟。
 * 将 RefactorIR 中的自然语言特征（文件名、函数名、类名）解析并映射为 AST 中具体的 Node ID。
 */
export class SemanticResolver {
  /**
   * @param astManager 已经初始化并加载了目标项目的 AST 管理器实例
   */
  constructor(private astManager: ASTManager) {}

  /**
   * 对大模型生成的指令集进行解析和坐标绑定
   * @param instructions 大模型输出的未经解析的 RefactorIR 指令列表
   * @returns 附加了 `resolved_target` (包含准确的 ast_node_id 和 置信度) 的新指令集
   */
  public resolve(instructions: any[]) {
    const resolved = [];
    for (const ir of instructions) {
      // 浅拷贝当前指令，准备附加解析结果
      const resolvedIr = { ...ir };
      // 提取目标特征：文件、符号名称、符号类型
      const { file, symbol_name, symbol_type } = ir.target;
      
      // 尝试在 AST 树中找到对应的源码文件
      const sourceFile = this.astManager.getSourceFile(file);
      
      if (sourceFile) {
        let targetNode = null;
        // 根据符号类型，在文件中寻找具体的声明节点
        if (symbol_type === "function") {
          targetNode = sourceFile.getFunction(symbol_name);
        } else if (symbol_type === "class") {
          targetNode = sourceFile.getClass(symbol_name);
        }
        // TODO: 可在此处继续扩展支持 interface, variable 等类型的节点解析
        
        if (targetNode) {
          // 如果找到节点，生成一个粗略的 Node ID。
          // 这里使用节点的起始和结束位置作为唯一标识，以便后续的 Executor 可以精确选中该代码块。
          const ast_node_id = `${targetNode.getStart()}-${targetNode.getEnd()}`;
          
          // 记录解析成功，置信度 1.0 (代表完全精确匹配)
          resolvedIr.resolved_target = { ast_node_id, confidence: 1.0 };
        } else {
          // 如果在文件中没找到对应符号名称的节点，解析失败
          resolvedIr.resolved_target = { ast_node_id: null, confidence: 0.0 };
        }
      } else {
         // 如果连目标文件都没找到，解析失败
         resolvedIr.resolved_target = { ast_node_id: null, confidence: 0.0 };
      }
      resolved.push(resolvedIr);
    }
    return { instructions: resolved };
  }
}