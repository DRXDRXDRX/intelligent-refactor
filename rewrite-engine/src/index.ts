import http from "http";
import { ASTManager } from "./astManager";
import { SemanticResolver } from "./semanticResolver";
import { RefactorExecutor } from "./refactorExecutor";
import { CodeAnalyzer } from "./analyzer";

// 设置 HTTP 服务端口，默认 8080
const PORT = process.env.PORT || 8080;

/**
 * Node.js 代码重写引擎 (AST 服务) 入口点
 * 提供简单的原生 HTTP JSON RPC 接口，供 Python 后端进行跨语言调用。
 * 
 * 职责包括：
 * 1. 提供沙箱内目标项目的 AST 分析服务
 * 2. 坏味检测及依赖关系提取
 * 3. 语义解析目标
 * 4. 执行具体的 RefactorIR 代码修改指令
 */
const server = http.createServer((req, res) => {
  // 健康检查接口
  if (req.url === "/health" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  // 仅接受 POST 请求进行 RPC 调用
  if (req.method === "POST") {
    let body = "";
    // 收集请求体数据
    req.on("data", chunk => {
      body += chunk.toString();
    });
    
    // 请求体接收完毕，开始处理路由
    req.on("end", () => {
      try {
        const payload = JSON.parse(body || "{}");
        const projectPath = payload.project_path;
        
        // ----------------------------------------------------
        // 接口：扫描项目工程结构
        // ----------------------------------------------------
        if (req.url === "/rpc/scan_project") {
          if (!projectPath) throw new Error("project_path required");
          const astManager = new ASTManager(projectPath);
          res.writeHead(200, { "Content-Type": "application/json" });
          // 返回文件列表及项目框架类型等元数据
          res.end(JSON.stringify(astManager.scanProject()));
        } 
        
        // ----------------------------------------------------
        // 接口：深度分析指定的源代码文件
        // ----------------------------------------------------
        else if (req.url === "/rpc/analyze_ast") {
          if (!projectPath || !payload.files) throw new Error("project_path and files required");
          const astManager = new ASTManager(projectPath);
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify(astManager.analyzeAst(payload.files)));
        } 
        
        // ----------------------------------------------------
        // 接口：构建文件之间的依赖关系图
        // ----------------------------------------------------
        else if (req.url === "/rpc/build_dependency_graph") {
          if (!projectPath || !payload.files) throw new Error("project_path and files required");
          const astManager = new ASTManager(projectPath);
          const analyzer = new CodeAnalyzer(astManager);
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify(analyzer.buildDependencyGraph(payload.files)));
        }
        
        // ----------------------------------------------------
        // 接口：代码坏味检测
        // ----------------------------------------------------
        else if (req.url === "/rpc/detect_code_smells") {
           const filesToAnalyze = payload.files || [];
           if (!projectPath && filesToAnalyze.length > 0) throw new Error("project_path required when files are provided");
           
           try {
               const astManager = new ASTManager(projectPath || "mock_path");
               const analyzer = new CodeAnalyzer(astManager);
               res.writeHead(200, { "Content-Type": "application/json" });
               res.end(JSON.stringify(analyzer.detectCodeSmells(filesToAnalyze)));
           } catch (err: any) {
               res.writeHead(200, { "Content-Type": "application/json" });
               res.end(JSON.stringify([])); // 降级处理：遇到 AST 解析错误时返回空数组
           }
        }
        
        // ----------------------------------------------------
        // 接口：语义解析（将模糊目标解析为精准的 AST 节点定位）
        // ----------------------------------------------------
        else if (req.url === "/rpc/resolve_targets") {
          if (!projectPath || !payload.instructions) throw new Error("project_path and instructions required");
          const astManager = new ASTManager(projectPath);
          const resolver = new SemanticResolver(astManager);
          res.writeHead(200, { "Content-Type": "application/json" });
          // 接收初始指令集，返回补充了详细定位信息（resolved_target）的指令集
          res.end(JSON.stringify(resolver.resolve(payload.instructions)));
        } 
        
        // ----------------------------------------------------
        // 接口：执行代码重构中间表示(IR)指令
        // ----------------------------------------------------
        else if (req.url === "/rpc/execute_refactor_ir") {
          if (!projectPath || !payload.instructions) throw new Error("project_path and instructions required");
          const astManager = new ASTManager(projectPath);
          const executor = new RefactorExecutor(astManager);
          res.writeHead(200, { "Content-Type": "application/json" });
          // 执行指令，产生 AST 变化并最终写入磁盘，返回修改的文件列表
          res.end(JSON.stringify(executor.execute(payload.instructions)));
        } 
        
        // ----------------------------------------------------
        // 兜底路由
        // ----------------------------------------------------
        else {
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ success: true }));
        }
      } catch (err: any) {
        // 全局异常处理，返回 400 及错误信息
        if (!res.headersSent) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: err.message }));
        }
      }
    });
    return;
  }

  // 404 处理
  res.writeHead(404);
  res.end("Not Found");
});

// 启动服务器
server.listen(PORT, () => {
  console.log(`Rewrite Engine running on port ${PORT}`);
});