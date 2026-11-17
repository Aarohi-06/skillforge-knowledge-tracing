import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server,AdaptivePage,AdaptiveQuestion,AdaptiveResultsView,App,RestartConfirmation
before(async()=>{
  server=await createServer({server:{middlewareMode:true,hmr:{port:0}}})
  ;({default:AdaptivePage,AdaptiveQuestion,AdaptiveResultsView}=await server.ssrLoadModule('/src/AdaptivePage.tsx'))
  App=(await server.ssrLoadModule('/src/App.tsx')).default
  ;({RestartConfirmation}=await server.ssrLoadModule('/src/DiagnosticPage.tsx'))
})
after(async()=>{await server?.close()})
const render=(component,props)=>renderToStaticMarkup(createElement(component,props))
const question={id:600,concept_id:1,title:'Array index',description:'Choose a complexity.',difficulty:'easy',options:['O(1)','O(n)']}
const state={question,session:{session_id:'session',next_position:0,answered_questions:0,status:'in_progress',current_question_eligible:true},selected:null,feedback:null,results:null,busy:false,error:null,canReconcile:false,storageWarning:false,pendingAnswer:false,totalQuestions:5,selectionReason:'Arrays has the lowest eligible BKT estimate. This is the backend reason.'}
const actions={concepts:[{id:1,name:'Arrays',description:null}],onSelect(){},onSubmit(){},onContinue(){},onRefresh(){}}

test('Dashboard preserves ordinary Practice, diagnostics and recommendations alongside adaptive entry',()=>{
  const html=render(App,{})
  for(const text of ['Adaptive Practice','Diagnostic Assessment','Recommended Next Steps','Practice','My Progress'])assert.ok(html.includes(text))
})
test('welcome explains progressive selection, ungraded purpose and mastery updates',()=>{
  const html=render(AdaptivePage,{concepts:[],onDashboard(){},onProgress(){}})
  for(const text of ['Approximately five questions','selected progressively','prerequisite eligibility','previous attempts','not a graded examination','Estimates update after each submitted answer','Start or Resume Adaptive Practice'])assert.ok(html.includes(text))
  assert.ok(!html.includes('Correct answer</h5>'))
})
test('actual backend selection reason is rendered safely without answer-key or explanation leakage',()=>{
  const html=render(AdaptiveQuestion,{...actions,state})
  assert.ok(html.includes(state.selectionReason))
  assert.ok(html.includes('Why this question was selected'))
  assert.ok(html.includes('Arrays'))
  assert.ok(html.includes('Question 1 · target 5'))
  assert.ok(html.includes('<progress'))
  assert.ok(html.includes('aria-labelledby="adaptive-question"'))
  assert.ok(html.includes('aria-pressed="false"'))
  assert.ok(!html.includes('Correct answer</h5>'))
  assert.ok(!html.includes('Explanation</h5>'))
  const escaped=render(AdaptiveQuestion,{...actions,state:{...state,selectionReason:'<img src=x onerror="alert(1)">'}})
  assert.ok(!escaped.includes('<img'));assert.ok(escaped.includes('&lt;img'))
  const missing=render(AdaptiveQuestion,{...actions,state:{...state,selectionReason:null}})
  assert.ok(missing.includes('No selection reason was returned'))
})
test('authorized correct and incorrect feedback remains attached to the submitted question',()=>{
  for(const is_correct of [true,false]){
    const feedback={session_id:'session',position:0,feedback:{question_id:600,selected_answer:is_correct?0:1,is_correct,correct_answer:0,explanation:'An authored explanation.',mastery_probability:0.3}}
    const html=render(AdaptiveQuestion,{...actions,state:{...state,feedback,selected:feedback.feedback.selected_answer}})
    for(const text of [is_correct?'Correct!':'Incorrect.','A. O(1)','An authored explanation.','Updated BKT mastery: 30.0%','Continue'])assert.ok(html.includes(text))
    assert.ok(html.includes('role="status"'))
    assert.ok(!html.includes('>Submit Answer<'))
  }
})
test('blocked assignments explain unmet prerequisites and disable fresh answers',()=>{
  const html=render(AdaptiveQuestion,{...actions,state:{...state,selected:0,session:{...state.session,current_question_eligible:false,blocked_reason:'Master Arrays before this concept.'}}})
  assert.ok(html.includes('Master Arrays before this concept.'))
  assert.ok(html.includes('Check Current Session'))
  assert.match(html,/<button[^>]*disabled=""[^>]*>Submit Answer/)
})
test('results distinguish accuracy, mastery and completion reason, including zero-answer sessions',()=>{
  const results={session_id:'session',answered_questions:2,target_questions:5,correct_answers:1,accuracy:0.5,completion_reason:'eligible_pool_exhausted',concepts:[{concept_id:1,concept_name:'Arrays',estimated_mastery:0,status:'weak'}],questions:[{position:0,is_correct:false,selection_reason:state.selectionReason}]}
  const html=render(AdaptiveResultsView,{results,onDashboard(){},onProgress(){}})
  for(const text of ['Finishing early is expected','Questions answered','2 / 5 target','1 / 2','Raw answer accuracy','50.0%','BKT estimated mastery','0.0%',state.selectionReason,'Dashboard Recommendations','My Progress'])assert.ok(html.includes(text))
  const empty=render(AdaptiveResultsView,{results:{...results,answered_questions:0,correct_answers:0,accuracy:null,concepts:[],questions:[]},onDashboard(){},onProgress(){}})
  assert.ok(empty.includes('Not available — no answers recorded'))
  assert.ok(!empty.includes('NaN'))
  assert.ok(!empty.includes('>0.0%</dd>'))
})
test('adaptive restart confirmation preserves diagnostic defaults and offers safe cancellation',()=>{
  const html=render(RestartConfirmation,{busy:false,onConfirm(){},onCancel(){},title:'Start a new adaptive session?',message:'Mastery and history are preserved.'})
  assert.ok(html.includes('Start a new adaptive session?'))
  assert.ok(html.includes('Mastery and history are preserved.'))
  assert.ok(html.includes('Keep Current Assessment'))
  assert.ok(html.includes('Confirm Restart'))
  assert.ok(render(RestartConfirmation,{busy:false,onConfirm(){},onCancel(){}}).includes('Restart this diagnostic?'))
})
