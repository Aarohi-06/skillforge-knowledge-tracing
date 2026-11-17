import assert from 'node:assert/strict'
import { test } from 'node:test'
import { adaptiveApi, AdaptiveError } from '../src/api/adaptive.ts'
import { createAdaptiveStore } from '../src/adaptiveStore.ts'

const sid = '11111111-1111-4111-8111-111111111111'
const sid2 = '22222222-2222-4222-8222-222222222222'
const question = (n) => ({ id: 600+n, concept_id: Math.floor(n/2)+1, title: `Question ${n+1}`, description:'Choose one.', difficulty:'easy', options:['First','Second'] })
const progress = (n=0, session_id=sid) => ({ session_id,student_id:1,status:n===5?'completed':'in_progress',created_at:'2026-11-17T00:00:00Z',updated_at:'2026-11-17T00:00:00Z',completed_at:n===5?'2026-11-17T00:01:00Z':null,target_questions:5,answered_questions:n,next_position:n===5?null:n,next_question:n===5?null:question(n), assigned_questions:n===5?5:n+1, selection_reason:n===5?null:`Actual backend selection reason ${n+1}`,current_question_eligible:n===5?null:true,blocked_reason:null,completion_reason:n===5?'target_reached':null })
const results = (session_id=sid) => ({ session_id,student_id:1,status:'completed',target_questions:5,answered_questions:5,correct_answers:3,accuracy:0.6,completion_reason:'target_reached',questions:[],mastery_basis:'last_adaptive_attempt',concepts:[{concept_id:1,concept_name:'Arrays',estimated_mastery:0.4,status:'learning',answered_questions:2}] })
const storage = () => { const map=new Map(); return { getItem:(k)=>map.get(k)??null,setItem:(k,v)=>map.set(k,v), map } }
const deferred = () => { let resolve; const promise=new Promise((yes)=>{resolve=yes}); return {promise,resolve} }
function backend() {
  let n=0, session=sid
  const recorded=new Map(), restarts=new Map(), calls={start:0,answer:0,updates:0,restart:[]}
  return {calls,api:{
    start:async()=>{calls.start++;return progress(n,session)},
    progress:async()=>progress(n,session),
    results:async()=>results(session),
    restart:async(_student,key)=>{calls.restart.push(key);if(!restarts.has(key)){session=sid2;n=0;restarts.set(key,progress(n,session))}return restarts.get(key)},
    answer:async(_student,id,payload)=>{
      calls.answer++
      const key=id+payload.submission_id
      if(recorded.has(key))return recorded.get(key)
      assert.equal(payload.question_id,question(n).id)
      const reply={session_id:id,position:n,feedback:{student_id:1,question_id:payload.question_id,selected_answer:payload.selected_answer,attempt_id:n+1,is_correct:payload.selected_answer===0,correct_answer:0,mastery_probability:0.4,explanation:`Authored explanation ${n+1}`}}
      recorded.set(key,reply);n++;calls.updates++;return reply
    },
  }}
}

test('typed client follows all actual adaptive routes, bodies and cancellation',async(t)=>{
  const sent=[], controller=new AbortController()
  t.mock.method(globalThis,'fetch',async(url,options)=>{sent.push({url,...options});return Response.json(progress())})
  const payload={question_id:600,selected_answer:0,submission_id:sid2}
  await adaptiveApi.start(1,controller.signal)
  await adaptiveApi.progress(1,sid,controller.signal)
  await adaptiveApi.answer(1,sid,payload,controller.signal)
  await adaptiveApi.results(1,sid,controller.signal)
  await adaptiveApi.restart(1,sid2,controller.signal)
  assert.deepEqual(sent.map((r)=>r.method),['POST','GET','POST','GET','POST'])
  assert.deepEqual(sent.map((r)=>new URL(r.url).pathname),['/students/1/adaptive-sessions/start',`/students/1/adaptive-sessions/${sid}`,`/students/1/adaptive-sessions/${sid}/answers`,`/students/1/adaptive-sessions/${sid}/results`,'/students/1/adaptive-sessions/restart'])
  assert.deepEqual(JSON.parse(sent[2].body),payload)
  assert.deepEqual(JSON.parse(sent[4].body),{request_id:sid2})
  assert.ok(sent.every((r)=>r.signal===controller.signal&&r.cache==='no-store'))
})
test('client reports missing students, stale sessions and non-JSON errors',async(t)=>{
  for(const [status,detail] of [[404,'Student not found'],[409,'Adaptive is not in progress']]){
    t.mock.method(globalThis,'fetch',async()=>Response.json({detail},{status}))
    await assert.rejects(adaptiveApi.start(1),(e)=>e instanceof AdaptiveError&&e.status===status&&e.message===detail)
  }
  t.mock.method(globalThis,'fetch',async()=>new Response('offline',{status:500}))
  await assert.rejects(adaptiveApi.start(1),/Could not load/)
})
test('welcome is inert; start/resume uses authoritative backend instead of a stale saved ID',async()=>{
  const disk=storage(), b=backend()
  disk.setItem('skillforge:adaptive:1:v1',JSON.stringify({version:1,student:1,sessionId:sid2,pending:null,restartId:null}))
  const store=createAdaptiveStore(1,b.api,disk)
  assert.equal(b.calls.start,0)
  await store.open()
  assert.equal(store.getSnapshot().session.session_id,sid)
  assert.equal(store.getSnapshot().question.id,600)
  assert.equal(store.getSnapshot().feedback,null)
})
test('five-question sequence preserves each feedback until Next and ends with real results',async()=>{
  const b=backend(),store=createAdaptiveStore(1,b.api,storage())
  await store.open()
  for(let i=0;i<5;i++){
    store.select(i%2)
    await store.submit()
    assert.equal(store.getSnapshot().question.id,600+i)
    assert.equal(store.getSnapshot().feedback.feedback.explanation,`Authored explanation ${i+1}`)
    await store.submit()
    assert.equal(b.calls.updates,i+1)
    await store.next()
  }
  assert.equal(store.getSnapshot().results.accuracy,0.6)
  assert.equal(store.getSnapshot().feedback,null)
  assert.equal(store.getSnapshot().question,null)
  assert.equal(b.calls.updates,5)
})
test('rapid repeated start and submit clicks make only one intended request',async()=>{
  const b=backend(),pending=deferred(),api={...b.api,start:()=>{b.calls.start++;return pending.promise}}
  const store=createAdaptiveStore(1,api,storage())
  const first=store.open();await store.open()
  assert.equal(b.calls.start,1)
  pending.resolve(progress());await first
  store.select(0)
  await Promise.all([store.submit(),store.submit(),store.submit()])
  assert.equal(b.calls.answer,1)
})
test('ambiguous failure locks selection, reuses the UUID and recovers the saved feedback after reload',async()=>{
  const b=backend(),disk=storage(),sent=[]
  const api={...b.api,answer:async(...args)=>{sent.push(args[2]);const result=await b.api.answer(...args);if(sent.length===1)throw new TypeError('Lost response');return result}}
  const store=createAdaptiveStore(1,api,disk)
  await store.open();store.select(1);await store.submit()
  assert.equal(store.getSnapshot().feedback,null)
  assert.equal(store.getSnapshot().pendingAnswer,true)
  store.select(0);assert.equal(store.getSnapshot().selected,1)
  const resumed=createAdaptiveStore(1,api,disk)
  await resumed.open()
  assert.deepEqual(sent[0],sent[1])
  assert.equal(b.calls.updates,1)
  assert.equal(resumed.getSnapshot().feedback.feedback.is_correct,false)
  await resumed.next()
  resumed.select(0);await resumed.submit()
  assert.notEqual(sent[1].submission_id,sent[2].submission_id)
})
test('retry in the same view also preserves the original answer UUID',async()=>{
  const b=backend(),sent=[]
  const api={...b.api,answer:async(...args)=>{sent.push(args[2]);if(sent.length===1)throw new Error('Network unavailable');return b.api.answer(...args)}}
  const store=createAdaptiveStore(1,api,storage())
  await store.open();store.select(0);await store.submit();await store.retry()
  assert.deepEqual(sent[0],sent[1]);assert.equal(b.calls.updates,1)
})
test('cancelled view ignores late async responses even when fetch ignores cancellation',async()=>{
  const delayed=deferred(),store=createAdaptiveStore(1,{...backend().api,start:()=>delayed.promise},storage())
  const pending=store.open();store.cancel();delayed.resolve(progress());await pending
  assert.equal(store.getSnapshot().session,null)
  assert.equal(store.getSnapshot().busy,false)
})
test('completed sessions load results without starting another session or submitting answers',async()=>{
  const b=backend(),store=createAdaptiveStore(1,{...b.api,start:async()=>progress(5)},storage())
  await store.open();assert.equal(store.getSnapshot().results.correct_answers,3);assert.equal(b.calls.answer,0)
})
test('failed result retrieval after final Next retries without submitting another answer',async()=>{
  const b=backend();let fail=true
  const store=createAdaptiveStore(1,{...b.api,results:async(...args)=>{if(fail){fail=false;throw new Error('Results unavailable')}return b.api.results(...args)}},storage())
  await store.open()
  for(let i=0;i<5;i++){store.select(0);await store.submit();await store.next()}
  assert.equal(store.getSnapshot().error,'Results unavailable')
  await store.retry();assert.equal(store.getSnapshot().results.answered_questions,5);assert.equal(b.calls.updates,5)
})
test('restart retries, including page reload, reuse one request key and clear old feedback',async()=>{
  const b=backend(),disk=storage();let first=true
  const api={...b.api,restart:async(...args)=>{const value=await b.api.restart(...args);if(first){first=false;throw new Error('Restart response lost')}return value}}
  const store=createAdaptiveStore(1,api,disk)
  await store.open();store.select(0);await store.submit();await store.restart()
  const resumed=createAdaptiveStore(1,api,disk);await resumed.open()
  assert.equal(b.calls.restart[0],b.calls.restart[1])
  assert.equal(resumed.getSnapshot().session.session_id,sid2)
  assert.equal(resumed.getSnapshot().feedback,null);assert.equal(resumed.getSnapshot().selected,null)
})
test('abandoned/stale state reconciles with current backend assessment',async()=>{
  const b=backend(),store=createAdaptiveStore(1,{...b.api,start:async()=>({...progress(),status:'abandoned',next_question:null})},storage())
  await store.open();assert.equal(store.getSnapshot().session.status,'abandoned')
  const disk=storage(),api={...b.api,answer:async()=>{throw new AdaptiveError('Adaptive is not in progress',409)}}
  const pending=createAdaptiveStore(1,api,disk)
  await pending.open();pending.select(0);await pending.submit()
  assert.equal(pending.getSnapshot().canReconcile,true)
  await pending.reconcile();assert.equal(pending.getSnapshot().pendingAnswer,false);assert.equal(pending.getSnapshot().error,null)
})
test('storage denial, malformed cache and mismatched student responses fail safely',async()=>{
  const b=backend(),store=createAdaptiveStore(1,b.api,{getItem:()=>'{bad',setItem:()=>{throw new Error('Blocked')}})
  await store.open();assert.equal(store.getSnapshot().storageWarning,true)
  const wrong=createAdaptiveStore(1,{...b.api,start:async()=>({...progress(),student_id:2})},storage())
  await wrong.open();assert.match(wrong.getSnapshot().error,/did not match/);assert.equal(wrong.getSnapshot().question,null)
})
test('incomplete local cache is discarded rather than leaving answer choices locked',async()=>{
  const disk=storage(),b=backend()
  disk.setItem('skillforge:adaptive:1:v1',JSON.stringify({version:1,student:1,sessionId:sid,restartId:null}))
  const store=createAdaptiveStore(1,b.api,disk)
  await store.open();store.select(0)
  assert.equal(store.getSnapshot().storageWarning,true)
  assert.equal(store.getSnapshot().selected,0)
  assert.equal(store.getSnapshot().pendingAnswer,false)
})

test('the backend chooses the next question and reason only after Continue',async()=>{
  const b=backend()
  const api={...b.api,progress:async()=>({...progress(1),next_question:{...question(1),id:1337},selection_reason:'A real server reason for an unexpected question ID.'})}
  const store=createAdaptiveStore(1,api,storage())
  await store.open();store.select(0);await store.submit()
  assert.equal(store.getSnapshot().question.id,600)
  assert.equal(store.getSnapshot().selectionReason,'Actual backend selection reason 1')
  await store.next()
  assert.equal(store.getSnapshot().question.id,1337)
  assert.equal(store.getSnapshot().selectionReason,'A real server reason for an unexpected question ID.')
  assert.equal(store.getSnapshot().selected,null)
})

test('zero-question pool exhaustion returns null accuracy and no invented estimates',async()=>{
  const b=backend(),session={...progress(),status:'completed',next_question:null,next_position:null,selection_reason:null,current_question_eligible:null,assigned_questions:0,completion_reason:'eligible_pool_exhausted'}
  const empty={...results(),answered_questions:0,correct_answers:0,accuracy:null,concepts:[],questions:[],completion_reason:'eligible_pool_exhausted'}
  const store=createAdaptiveStore(1,{...b.api,start:async()=>session,results:async()=>empty},storage())
  await store.open()
  assert.deepEqual(store.getSnapshot().results,empty)
  assert.equal(store.getSnapshot().question,null)
  assert.equal(b.calls.answer,0)
})

test('early completion after two saved answers does not attempt a third question',async()=>{
  const b=backend()
  const api={...b.api,progress:async()=> b.calls.updates===2 ? {...progress(2),status:'completed',next_question:null,next_position:null,completion_reason:'eligible_pool_exhausted'} : b.api.progress(),
    results:async()=>({...results(),answered_questions:2,correct_answers:1,accuracy:0.5,completion_reason:'eligible_pool_exhausted'})}
  const store=createAdaptiveStore(1,api,storage());await store.open()
  for(let i=0;i<2;i++){store.select(i);await store.submit();await store.next()}
  assert.equal(store.getSnapshot().results.answered_questions,2)
  assert.equal(store.getSnapshot().results.completion_reason,'eligible_pool_exhausted')
  assert.equal(b.calls.updates,2)
})

test('currently locked assignments cannot be selected or submitted',async()=>{
  const b=backend();let blocked=true
  const api={...b.api,start:async()=>({...progress(),current_question_eligible:!blocked,blocked_reason:blocked?'Master Arrays first.':null})}
  const store=createAdaptiveStore(1,api,storage());await store.open()
  store.select(0);await store.submit()
  assert.equal(store.getSnapshot().selected,null)
  assert.equal(b.calls.answer,0)
  blocked=false;await store.reconcile();store.select(0);await store.submit()
  assert.equal(b.calls.updates,1)
})

test('adaptive persistence never consumes diagnostic retry storage',async()=>{
  const disk=storage(),diagnostic='skillforge:diagnostic:1:v1'
  disk.setItem(diagnostic,'diagnostic data remains untouched')
  const store=createAdaptiveStore(1,backend().api,disk);await store.open()
  assert.equal(disk.getItem(diagnostic),'diagnostic data remains untouched')
  assert.ok(disk.getItem('skillforge:adaptive:1:v1'))
})
