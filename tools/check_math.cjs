// Optional MathJax 3.2.2 check. No browser or application window is launched.
const fs=require('node:fs'), path=require('node:path'), crypto=require('node:crypto'), assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const outputFlag=process.argv.indexOf('--out');
if(outputFlag>=0 && !process.argv[outputFlag+1])throw Error('--out requires a file path.');
const output=outputFlag>=0 ? path.resolve(process.argv[outputFlag+1]) : path.join(root,'.runtime/math-validation.json');
const packageRoot=process.env.MATHJAX_PACKAGE;
if(!packageRoot)throw Error('Set MATHJAX_PACKAGE to an installed mathjax-full 3.2.2 package directory.');
const load=name=>require(path.join(packageRoot,'js',name));
const {mathjax}=load('mathjax.js'),{TeX}=load('input/tex.js'),{SVG}=load('output/svg.js');
const {liteAdaptor}=load('adaptors/liteAdaptor.js'),{RegisterHTMLHandler}=load('handlers/html.js');
load('input/tex/base/BaseConfiguration.js');load('input/tex/ams/AmsConfiguration.js');
assert.equal(require(path.join(packageRoot,'package.json')).version,'3.2.2');
const adaptor=liteAdaptor();RegisterHTMLHandler(adaptor);
const tex=new TeX({packages:['base','ams'],formatError:(_,error)=>{throw error;}});
const doc=mathjax.document('',{InputJax:tex,OutputJax:new SVG({fontCache:'none'})});
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const pages=['README.md','architecture.md','api.md','metrics.md','experiment-design.md','results.md','demo.md','scope.md','spec-decisions.md','ai-use.md'];
const files=['README.md',...pages.map(n=>'docs/'+n)];
const expressions=[],sources=[];
for(const file of files){
  const bytes=fs.readFileSync(path.join(root,file)),lines=bytes.toString('utf8').split(/\r?\n/),before=expressions.length;
  let fence=null,display=false,parts=[],start=0;
  for(let i=0;i<lines.length;i++){
    const line=lines[i],marker=line.trim();
    if(marker.startsWith('```')){
      if(fence===null){fence=marker.slice(3).trim();if(fence==='math'){parts=[];start=i+2;}}
      else{if(fence==='math')expressions.push({file,line:start,mode:'display',latex:parts.join('\n')});fence=null;}
    }else if(fence!==null){if(fence==='math')parts.push(line);}
    else if(marker==='$$'){
      if(!display){display=true;parts=[];start=i+2;}
      else{expressions.push({file,line:start,mode:'display',latex:parts.join('\n')});display=false;}
    }else if(display)parts.push(line);
    else for(const match of line.replace(/`[^`]*`/g,'').matchAll(/(?<!\\)\$(?!\$)([^$\n]+?)(?<!\\)\$/g))expressions.push({file,line:i+1,mode:'inline',latex:match[1]});
  }
  assert.equal(fence,null,file);assert.equal(display,false,file);
  if(expressions.length>before)sources.push({path:file,sha256:hash(bytes)});
}
function convert(latex,display){
  const result=adaptor.outerHTML(doc.convert(latex,{display}));
  assert(!result.includes('data-mml-node="merror"'),latex);
  return result;
}
for(const item of expressions){assert(!item.latex.includes('\\operatorname'));convert(item.latex,item.mode==='display');}
assert.throws(()=>convert('\\frac{1}{',true));assert.throws(()=>convert('\\notAProjectCommand',true));
const display=expressions.filter(x=>x.mode==='display').length;assert(display>0,'No display expressions found.');
const report={author:'Paco',status:'passed',source_files:sources,renderer:'MathJax 3.2.2, base and ams packages, SVG output with lite adaptor',
  display_expressions:display,inline_expressions:expressions.length-display,rendered_expressions:expressions.length,
  strict_parser:'passed',malformed_expression_rejected:true,unknown_command_rejected:true,
  browser_preview:'not performed; local headless parser check',
  github_hosted_rendering:'not certified by this local check',scope:'Local parsing and SVG conversion; not a GitHub preview certification'};
fs.mkdirSync(path.dirname(output),{recursive:true});
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
console.log(`PASS: ${expressions.length} expressions (${display} display); strict parser and SVG conversion; invalid inputs rejected.`);
