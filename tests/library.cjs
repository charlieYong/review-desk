// 首页方案目录：定位登记、历史回填、失效恢复与登记故障，全部使用独立临时目录。
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'review-desk-library-'));
const content=path.join(temp,'content'),project=path.join(temp,'project'),state=path.join(temp,'state');
for(const dir of [content,project,state])fs.mkdirSync(dir);
const file=path.join(project,'中文 空格.md'),direct=path.join(project,'direct.html'),old=path.join(project,'old.md');
fs.writeFileSync(file,'# 外部方案\n\n初始版本');fs.writeFileSync(direct,'<h1>直接打开</h1><p>正文</p>');
fs.writeFileSync(old,'# 历史方案');fs.writeFileSync(content+'/same.md','# 目录内方案');
const stateFile=source=>path.join(state,crypto.createHash('sha256').update(source).digest('hex')+'.json');
const oldState={documentId:old,version:0,imports:[],state:{round:1,revision:'old-revision',entries:[],archives:[]}};
fs.writeFileSync(stateFile(old),JSON.stringify(oldState));
const broken=path.join(state,'a'.repeat(64)+'.json');fs.writeFileSync(broken,'broken JSON');
let server,browser,base,logs='';
async function start(port=0){
  server=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'..','server.py'),'--directory',content,'--state-directory',state,'--bind','127.0.0.1','--port',String(port)],{stdio:['ignore','pipe','pipe']});
  base=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error('启动超时 '+logs)),10000);server.stderr.on('data',b=>logs+=b);server.once('exit',()=>{clearTimeout(timer);reject(Error(logs))});server.stdout.on('data',b=>{out+=b;const m=out.match(/Review Desk: (http:\/\/[^\s]+)/);if(m){clearTimeout(timer);resolve(m[1])}})});
}
async function stop(){if(server?.exitCode===null)await new Promise(resolve=>{server.once('exit',resolve);server.kill()})}
function pass(name){console.log('PASS: '+name)}
(async()=>{try{
  await start();browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH});
  const p=await browser.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
  const get=async url=>p.request.get(base+url);
  const files=async()=>{const r=await get('/_preview/files');assert.equal(r.status(),200);return r.json()};
  const locate=async source=>{const r=await get('/_preview/locate?path='+encodeURIComponent(source));assert.equal(r.status(),200);return (await r.json()).page};
  const review=async page=>{const r=await get('/_preview/review?page='+encodeURIComponent(page));assert.equal(r.status(),200);return r.json()};
  const find=async source=>(await files()).find(f=>f.name===source);
  const refresh=async()=>{const response=p.waitForResponse(r=>r.url().endsWith('/_preview/files'));await p.getByRole('button',{name:/刷新列表/}).click();await response;await p.waitForFunction(()=>!document.querySelector('#status').textContent.includes('失败'))};

  let list=await files();assert(list.some(f=>f.name===old&&f.available));assert.deepEqual(JSON.parse(fs.readFileSync(stateFile(old))),oldState);
  assert(logs.includes('跳过无法读取的旧批注记录'));assert(fs.readFileSync(broken,'utf8')==='broken JSON');
  pass('历史无批注记录回填；坏记录报告且不阻断、不改写旧批注');

  const page=await locate(file);assert((await find(file)).available);assert(!fs.existsSync(stateFile(file)));
  const catalog=path.join(state,'catalog.json'),before=fs.statSync(catalog).mtimeMs;
  await locate(file);await files();assert.equal(fs.statSync(catalog).mtimeMs,before);
  fs.writeFileSync(file,'# 定位后修改\n\n审查应从这一版开始。');
  const reviewed=await review(page);assert.equal(reviewed.state.revision,crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'));
  pass('定位即收录、重复登记不写盘；定位不提前创建审查轮次');

  await p.goto(base+'/_review?page='+encodeURIComponent('/_fs'+direct));await p.frameLocator('#page').getByRole('heading',{name:'直接打开'}).waitFor();
  assert((await find(direct)).available);assert.equal(await p.locator('#count').textContent(),'0');
  pass('绕过定位接口直接打开外部 HTML，也收录未批注方案');

  fs.symlinkSync(file,project+'/alias.md');fs.symlinkSync(content+'/same.md',content+'/alias.md');
  assert.equal(await locate(project+'/alias.md'),page);
  assert.equal(await locate(content+'/same.md'),'/same.md');assert.equal(await locate(content+'/alias.md'),'/same.md');
  fs.writeFileSync(project+'/same.md','# 外部同名方案');await locate(project+'/same.md');
  list=await files();assert.equal(list.filter(f=>f.url===page).length,1);assert.equal(list.filter(f=>f.url==='/same.md').length,1);assert(!list.some(f=>f.name==='alias.md'));
  assert(list.some(f=>f.name===project+'/same.md'));assert(list.some(f=>f.name==='same.md'));
  await p.goto(base+'/');await p.locator('#search').fill(project);await p.getByRole('link',{name:'中文 空格.md',exact:true}).waitFor();
  await p.getByRole('button',{name:'HTML',exact:true}).click();assert.equal(await p.locator('.file-row').count(),1);assert.equal(await p.locator('.file-info a').textContent(),'direct.html');
  await p.getByRole('button',{name:'全部',exact:true}).click();await p.getByRole('link',{name:'中文 空格.md',exact:true}).click();await p.frameLocator('#page').getByRole('heading',{name:'定位后修改'}).waitFor();
  assert.equal(new URL(p.url()).searchParams.get('page'),page);
  pass('真实路径去重、同名异目录隔离、中文空格路径、按目录搜索及类型筛选');

  const beforeState=fs.readFileSync(stateFile(file),'utf8');fs.unlinkSync(file);
  assert.equal((await find(file)).available,false);
  await p.goto(base+'/');await p.getByRole('link',{name:'old.md',exact:true}).waitFor();assert.equal(await p.getByRole('link',{name:'中文 空格.md',exact:true}).count(),0);
  await p.getByRole('button',{name:/失效方案/}).click();await p.getByText('中文 空格.md',{exact:true}).waitFor();assert.equal(await p.locator('#list a').count(),0);
  assert.equal(fs.readFileSync(stateFile(file),'utf8'),beforeState);
  fs.writeFileSync(file,'# 文件恢复');await refresh();await p.waitForFunction(()=>document.querySelector('#missingCount').textContent==='0');
  await p.getByRole('button',{name:/有效方案/}).click();await p.getByRole('link',{name:'中文 空格.md',exact:true}).waitFor();
  assert.equal(fs.readFileSync(stateFile(file),'utf8'),beforeState);
  fs.chmodSync(file,0);assert.equal((await find(file)).available,false);fs.chmodSync(file,0o600);assert.equal((await find(file)).available,true);
  fs.utimesSync(file,new Date('2030-01-01'),new Date('2030-01-01'));list=await files();assert.equal(list[0].name,file);
  await p.setViewportSize({width:390,height:844});await refresh();assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  pass('失效方案单独显示、删除及权限恢复保留批注、真实时间排序、手机布局');

  const port=new URL(base).port;await stop();await start(port);
  assert((await find(file)).available);assert((await find(direct)).available);
  // 旧记录在首次回填后出现仍可补入。
  const later=project+'/later.md';fs.writeFileSync(later,'# 晚到记录');fs.writeFileSync(stateFile(later),JSON.stringify({...oldState,documentId:later}));
  assert((await find(later)).available);
  pass('服务重启后列表持久化、旧记录可持续回填');

  // 注入真实文件系统写入故障，验证错误语义与共享批注独立可用。
  fs.renameSync(catalog,catalog+'.saved');fs.mkdirSync(path.join(state,'catalog.tmp'));
  let response=await get('/_preview/locate?path='+encodeURIComponent(file));assert.equal(response.status(),500);assert.match((await response.json()).error,/登记失败/);
  await p.goto(base+'/');await p.locator('#search').fill(file);await p.getByRole('button',{name:'打开批注'}).click();await p.waitForFunction(()=>document.querySelector('#localStatus').textContent.includes('登记失败'));
  await p.goto(base+'/_review?page='+encodeURIComponent(page));await p.frameLocator('#page').getByRole('heading',{name:'文件恢复'}).waitFor();await p.locator('#catalogStatus').getByText(/登记未完成/).waitFor();
  await p.locator('#next').click();await p.waitForFunction(()=>document.querySelector('#round').textContent==='第 2 轮审查');
  await p.locator('#note').fill('登记故障仍能保存批注');await p.locator('#save').click();await p.waitForFunction(()=>document.querySelector('#note').value==='');assert.equal(await p.locator('#count').textContent(),'1');
  assert.match(await p.locator('#catalogStatus').textContent(),/登记未完成/);
  fs.rmdirSync(path.join(state,'catalog.tmp'));fs.renameSync(catalog+'.saved',catalog);
  await p.evaluate(async()=>{await syncReview()});assert.equal(await p.locator('#catalogStatus').textContent(),'');
  const saved=await review(page);assert.equal(saved.state.entries[0].note,'登记故障仍能保存批注');
  pass('目录写入失败如实返回、首页提示、直接链接仍能打开及保存、恢复后清除警告');

  fs.writeFileSync(catalog,'invalid catalog');response=await get('/_preview/files');assert.equal(response.status(),500);assert.match((await response.json()).error,/目录读写失败/);assert.equal(fs.readFileSync(catalog,'utf8'),'invalid catalog');
  assert.match((await review(page)).catalogWarning,/登记未完成/);assert.equal(fs.readFileSync(catalog,'utf8'),'invalid catalog');
  assert.deepEqual(errors,[]);pass('损坏目录明确失败且不覆盖原文件；无浏览器 JS 错误');
}finally{if(browser)await browser.close();await stop();fs.rmSync(temp,{recursive:true,force:true})}})().catch(e=>{console.error(e);process.exitCode=1});
