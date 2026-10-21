// 两个独立浏览器上下文，使用临时服务与项目目录复现共享和归属问题。
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'review-desk-shared-'));
const content=path.join(temp,'content'),project=path.join(temp,'project'),stateDir=path.join(temp,'state');
fs.mkdirSync(content);fs.mkdirSync(project);
fs.writeFileSync(content+'/same.md','# 共享方案\n\n原文段落。');
fs.writeFileSync(project+'/same.md','# 项目方案\n\n![图片](pic.svg)\n\n原文段落。');
fs.writeFileSync(project+'/pic.svg','<svg xmlns="http://www.w3.org/2000/svg" width="80" height="20"></svg>');
let server,browser,base;const failures=[],requests=[];
async function start(port=0){
  const args=[path.join(__dirname,'..','server.py'),'--directory',content,'--bind','127.0.0.1','--port',String(port)];
  // 修复前也能运行相同用例；新版本明确指定临时状态目录。
  if(fs.readFileSync(args[0],'utf8').includes("add_argument('--state-directory'"))args.push('--state-directory',stateDir);
  server=spawn(process.env.PYTHON||'python3',args,{stdio:['ignore','pipe','pipe']});
  base=await new Promise((resolve,reject)=>{let out='',err='';const timer=setTimeout(()=>reject(Error(err||'启动超时')),10000);server.stderr.on('data',b=>err+=b);server.once('exit',()=>{clearTimeout(timer);reject(Error(err))});server.stdout.on('data',b=>{out+=b;const m=out.match(/Review Desk: (http:\/\/[^\s]+)/);if(m){clearTimeout(timer);resolve(m[1])}})});
}
async function stop(){if(server?.exitCode===null)await new Promise(r=>{server.once('exit',r);server.kill()})}
async function open(context,page){const p=await context.newPage();p.on('request',r=>{if(r.method()!=='GET')requests.push([r.method(),new URL(r.url()).pathname])});await p.goto(base+'/_review?page='+encodeURIComponent(page));await p.frameLocator('#page').locator('h1').waitFor();return p}
async function save(p,note){await p.locator('#note').fill(note);await p.locator('#save').click();await p.waitForFunction(()=>document.querySelector('#note').value==='')}
async function sync(p){await p.evaluate(async()=>{window.dispatchEvent(new Event('focus'));if(typeof syncReview==='function')await syncReview()})}
async function notes(p){return p.locator('#list .card p').allTextContents()}
async function check(name,fn){try{await fn();console.log('PASS: '+name)}catch(e){failures.push(name);console.log('FAIL: '+name+' — '+e.message.split('\n')[0])}}
(async()=>{try{
await start();browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH});
const a=await browser.newContext(),b=await browser.newContext();
const p=await open(a,'/same.md'),q=await open(b,'/_fs'+content+'/same.md');
await check('普通路径与绝对路径共享；并发新增不丢失',async()=>{
  await Promise.all([save(p,'来自 A'),save(q,'来自 B')]);await Promise.all([sync(p),sync(q)]);
  assert.deepEqual((await notes(p)).sort(),['来自 A','来自 B']);assert.deepEqual((await notes(q)).sort(),['来自 A','来自 B']);
});
await check('不同目录同名文件隔离、项目文档无需复制、相对资源',async()=>{
  const r=await open(b,'/_fs'+project+'/same.md');assert.deepEqual(await notes(r),[]);
  assert(await r.frameLocator('#page').locator('img').evaluate(el=>el.complete&&el.naturalWidth===80));
  await save(r,'项目内意见');assert(!fs.existsSync(content+'/pic.svg'));assert.equal(fs.readdirSync(content).length,1);await r.close();
});
await check('刷新、服务重启后新客户端读取共享批注',async()=>{
  await p.reload();await p.frameLocator('#page').locator('h1').waitFor();assert.deepEqual((await notes(p)).sort(),['来自 A','来自 B']);
  const port=new URL(base).port;await stop();await start(port);const c=await browser.newContext(),r=await open(c,'/same.md');assert.deepEqual((await notes(r)).sort(),['来自 A','来自 B']);await c.close();
});
await check('项目原地更新、版本提示、轮次及历史跨客户端保留',async()=>{
  const r=await open(a,'/_fs'+project+'/same.md'),s=await open(b,'/_fs'+project+'/same.md'),url=r.url();
  fs.writeFileSync(project+'/same.md','# 项目第二版\n\n![图片](pic.svg)\n\n原文段落。');await sync(r);
  await r.locator('#update').waitFor({state:'visible'});await r.locator('#next').click();await r.frameLocator('#page').getByRole('heading',{name:'项目第二版'}).waitFor();
  await sync(s);assert.equal(r.url(),url);assert.equal(await s.locator('#round').textContent(),'第 2 轮审查');assert.equal(await s.locator('#historyCount').textContent(),'1');assert.equal(await s.locator('#count').textContent(),'0');
  await r.close();await s.close();
});
await check('本地旧批注自动导入、备份保留、删除后不重复导入',async()=>{
  const c=await browser.newContext();await c.addInitScript(({origin,abs})=>{if(!localStorage.getItem('seeded')){localStorage.setItem('review-desk:v1:'+origin+abs,JSON.stringify([{id:'legacy',quote:'',note:'本地遗留'}]));localStorage.setItem('seeded','1')}},{origin:base,abs:'/_fs'+content+'/same.md'});
  const r=await open(c,'/same.md');assert((await notes(r)).includes('本地遗留'));assert(await r.evaluate(()=>Object.keys(localStorage).some(k=>k.startsWith('review-desk:v1:'))));
  await r.locator('#list .card').filter({hasText:'本地遗留'}).getByRole('button',{name:'删除',exact:true}).click();await r.reload();await r.frameLocator('#page').locator('h1').waitFor();assert(!(await notes(r)).includes('本地遗留'));await c.close();
});
await check('自动轮询可见、保留另一端未保存草稿',async()=>{
  await p.locator('#note').fill('轮询期间草稿');await save(q,'等待轮询的意见');
  await p.waitForFunction(()=>document.querySelector('#list').textContent.includes('等待轮询的意见'),{},{timeout:20000});
  assert.equal(await p.locator('#note').inputValue(),'轮询期间草稿');await p.locator('#cancel').click();
});
await check('同条并发编辑返回 409 并保留失败方草稿',async()=>{
  await Promise.all([sync(p),sync(q)]);
  const card=x=>x.locator('#list .card').filter({hasText:'来自 A'});
  await card(p).getByRole('button',{name:'编辑',exact:true}).click();await card(q).getByRole('button',{name:'编辑',exact:true}).click();
  await p.locator('#note').fill('A 修改成功');await q.locator('#note').fill('B 冲突草稿');
  await p.locator('#save').click();await p.waitForFunction(()=>document.querySelector('#note').value==='');
  const rejected=q.waitForResponse(r=>r.url().includes('/_preview/review')&&r.request().method()==='POST');
  await q.locator('#save').click();assert.equal((await rejected).status(),409);
  await q.waitForFunction(()=>/其他客户端/.test(document.querySelector('#status').textContent));
  assert.equal(await q.locator('#note').inputValue(),'B 冲突草稿');assert((await notes(q)).includes('A 修改成功'));await q.locator('#cancel').click();
});
await check('保存请求失败不清空草稿，恢复后可提交',async()=>{
  await q.route('**/_preview/review',route=>route.request().method()==='POST'?route.abort():route.continue());
  await q.locator('#note').fill('网络失败草稿');await q.locator('#save').click();
  await q.waitForFunction(()=>document.querySelector('#status').textContent.includes('无法确认'));
  assert.equal(await q.locator('#note').inputValue(),'网络失败草稿');
  await q.unroute('**/_preview/review');await q.locator('#save').click();await q.waitForFunction(()=>document.querySelector('#note').value==='');
});
await check('含空格中文文件、符号链接、查询参数统一真实文件身份',async()=>{
  const filename='中文 空格.md';fs.writeFileSync(content+'/'+filename,'# 编码方案');fs.symlinkSync(content+'/'+filename,content+'/alias.md');
  const get=async page=>(await(await p.request.get(base+'/_preview/review?page='+encodeURIComponent(page))).json());
  const normal=await get('/'+encodeURIComponent(filename)+'?raw=1'),absolute=await get('/_fs'+content+'/'+encodeURIComponent(filename)),alias=await get('/alias.md');
  assert.equal(normal.documentId,absolute.documentId);assert.equal(normal.documentId,alias.documentId);
  assert.equal((await(await p.request.get(base+'/_preview/locate?path='+encodeURIComponent(content+'/'+filename))).json()).page,normal.page);
});
await check('旧对象格式保留轮次、版本、历史及已解决状态；异版导入归档',async()=>{
  fs.writeFileSync(content+'/legacy.md','# 迁移方案');
  const legacy={round:3,revision:'old-revision',entries:[{id:'cur',quote:'',note:'第三轮旧意见'}],archives:[{round:2,revision:'older',archivedAt:123,entries:[{id:'hist',quote:'',note:'历史意见',resolved:true}]}]};
  const c=await browser.newContext();await c.addInitScript(({origin,legacy})=>localStorage.setItem('review-desk:v1:'+origin+'/legacy.md',JSON.stringify(legacy)),{origin:base,legacy});
  const r=await open(c,'/legacy.md');assert.equal(await r.locator('#round').textContent(),'第 3 轮审查');assert.equal(await r.locator('#count').textContent(),'1');assert.equal(await r.locator('#historyCount').textContent(),'1');assert(await r.locator('#update').isVisible());
  await r.locator('#history summary').click();assert.equal(await r.locator('.history-card .tag').textContent(),'已解决');
  const d=await browser.newContext();await d.addInitScript(({origin})=>localStorage.setItem('review-desk:v1:'+origin+'/legacy.md',JSON.stringify({round:1,revision:'other-version',entries:[{id:'other',quote:'',note:'另一电脑旧意见'}],archives:[]})),{origin:base});
  const t=await open(d,'/legacy.md');assert.equal(await t.locator('#round').textContent(),'第 3 轮审查');assert.equal(await t.locator('#count').textContent(),'1');assert.equal(await t.locator('#historyCount').textContent(),'2');await c.close();await d.close();
});
await check('无批注的首次阅读也固定共享版本，更新不会隐式切轮',async()=>{
  fs.writeFileSync(content+'/empty.md','# 首次阅读');
  const get=async()=>(await(await p.request.get(base+'/_preview/review?page=/empty.md')).json());
  const initial=await get();fs.writeFileSync(content+'/empty.md','# 修改后的阅读');
  const updated=await get();assert.equal(initial.state.revision,updated.state.revision);assert.equal(updated.state.round,1);
  const c=await browser.newContext(),r=await open(c,'/empty.md');assert(await r.locator('#update').isVisible());await c.close();
});
await check('并发切轮与新增：旧意见完整归档，过期请求明确冲突',async()=>{
  const get=async()=>(await(await p.request.get(base+'/_preview/review?page=/same.md')).json());
  const before=await get(),common={page:'/same.md',round:before.state.round,revision:before.state.revision};
  fs.writeFileSync(content+'/same.md','# 共享方案第二版');
  const responses=await Promise.all([p.request.post(base+'/_preview/review',{data:{...common,action:'add',entry:{id:'racing',quote:'',note:'切轮并发意见'}}}),p.request.post(base+'/_preview/review',{data:{...common,action:'next'}})]);
  assert.equal(responses[1].status(),200);assert([200,409].includes(responses[0].status()));
  const after=await get();assert.equal(after.state.round,before.state.round+1);assert.equal(after.state.entries.length,0);
  const archived=after.state.archives.at(-1).entries;assert.equal(archived.length,before.state.entries.length+(responses[0].status()===200?1:0));
  const stale=await p.request.post(base+'/_preview/review',{data:{...common,action:'add',entry:{id:'stale',quote:'',note:'过期保存'}}});assert.equal(stale.status(),409);
});
console.log('保存/读取观测: '+JSON.stringify({writeRequests:requests,localKeys:await p.evaluate(()=>Object.keys(localStorage))}));
assert.deepEqual(failures,[], '失败用例: '+failures.join('、'));
}finally{if(browser)await browser.close();await stop();fs.rmSync(temp,{recursive:true,force:true})}})().catch(e=>{console.error(e.message);process.exitCode=1});
