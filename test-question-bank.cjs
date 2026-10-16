const fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.join(__dirname,'data','questions');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
const seen=new Set(),counts={};let total=0,leaks=0;
for(let difficulty=1;difficulty<=10;difficulty++){
  const level=manifest.levels[String(difficulty)];assert(level,'missing level '+difficulty);
  let levelCount=0;
  for(const chunk of level.chunks){
    const rows=JSON.parse(fs.readFileSync(path.join(root,chunk.file),'utf8'));
    assert.equal(rows.length,chunk.count,chunk.file+' count');
    for(const row of rows){
      assert(Array.isArray(row)&&row.length===3);
      const [answer,clue,d]=row;
      assert(/^[А-Я]{3,18}$/.test(answer),answer);
      assert(typeof clue==='string'&&clue.length>=3&&clue.length<=180,answer+' clue length');
      assert.equal(d,difficulty,answer+' difficulty');
      const key=answer+'\0'+clue.toLocaleLowerCase('ru');assert(!seen.has(key),'duplicate '+answer);seen.add(key);
      const normal=clue.toLocaleUpperCase('ru').replaceAll('Ё','Е');
      if(new RegExp('(^|[^А-Я])'+answer+'([^А-Я]|$)').test(normal))leaks++;
      total++;levelCount++;
    }
  }
  assert.equal(levelCount,level.count,'manifest level '+difficulty);counts[difficulty]=levelCount;
}
assert(total>200000);assert.equal(total,manifest.total);assert.equal(leaks,0,'clues containing answers');
console.log(JSON.stringify({total,counts,unique:seen.size,leaks,source:manifest.source},null,2));
