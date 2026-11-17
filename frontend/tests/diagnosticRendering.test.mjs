import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server, DiagnosticPage, DiagnosticQuestion, DiagnosticResultsView, RestartConfirmation, App
before(async()=>{
  server=await createServer({server:{middlewareMode:true,hmr:{port:0}}})
  ;({default:DiagnosticPage,DiagnosticQuestion,DiagnosticResultsView,RestartConfirmation}=await server.ssrLoadModule('/src/DiagnosticPage.tsx'))
  App=(await server.ssrLoadModule('/src/App.tsx')).default
})
after(async()=>{await server?.close()})
const render=(component,props)=>renderToStaticMarkup(createElement(component,props))
const question={id:600,concept_id:1,title:'Array index',description:'Choose a complexity.',difficulty:'easy',options:['O(1)','O(n)']}
const state={question,session:{session_id:'session',next_position:0,answered_questions:0,status:'in_progress'},selected:null,feedback:null,results:null,busy:false,error:null,canReconcile:false,storageWarning:false,pendingAnswer:false,totalQuestions:6}
const actions={concepts:[{id:1,name:'Arrays',description:null}],onSelect(){},onSubmit(){},onNext(){}}

test('Dashboard adds an accessible diagnostic entry without removing recommendations or navigation',()=>{
  const html=render(App,{})
  assert.ok(html.includes('Diagnostic Assessment'))
  assert.ok(html.includes('Recommended Next Steps'))
  assert.ok(html.includes('Main navigation'))
  assert.ok(html.includes('My Progress'))
})
test('welcome explains six-question scope, ungraded purpose, and existing mastery preservation',()=>{
  const html=render(DiagnosticPage,{concepts:[],onDashboard(){},onProgress(){}})
  for(const text of ['Six questions','Arrays, Time Complexity, and Recursion','not a graded exam','existing mastery is not reset','Start or Resume Assessment'])assert.ok(html.includes(text))
  assert.ok(!html.includes('Correct answer</h5>'))
})
test('question is accessible, labels concept and progress, and reveals no pre-submission explanation',()=>{
  const html=render(DiagnosticQuestion,{...actions,state})
  assert.ok(html.includes('Arrays'))
  assert.ok(html.includes('Question 1 of 6'))
  assert.ok(html.includes('<progress'))
  assert.ok(html.includes('for="diagnostic-progress"'))
  assert.ok(html.includes('aria-labelledby="diagnostic-question"'))
  assert.ok(html.includes('aria-pressed="false"'))
  assert.match(html,/<button[^>]*disabled=""[^>]*>Submit Answer/)
  assert.ok(!html.includes('Correct answer</h5>'))
  assert.ok(!html.includes('Explanation</h5>'))
})
test('authorized feedback is reused safely, and final feedback offers View Results',()=>{
  const feedback={session_id:'session',position:5,feedback:{question_id:600,selected_answer:1,is_correct:false,correct_answer:0,explanation:'An authored explanation.',mastery_probability:0.3}}
  const html=render(DiagnosticQuestion,{...actions,state:{...state,feedback,selected:1}})
  assert.ok(html.includes('Incorrect.'))
  assert.ok(html.includes('An authored explanation.'))
  assert.ok(html.includes('Updated BKT mastery: 30.0%'))
  assert.ok(html.includes('View Results'))
  assert.ok(html.includes('role="status"'))
  assert.ok(!html.includes('>Submit Answer<'))
})
test('confirmation offers a safe cancel and describes preserved mastery/history',()=>{
  const html=render(RestartConfirmation,{busy:false,onConfirm(){},onCancel(){}})
  assert.ok(html.includes('Restart this diagnostic?'))
  assert.ok(html.includes('mastery and all saved attempts will remain'))
  assert.ok(html.includes('Keep Current Assessment'))
  assert.ok(html.includes('Confirm Restart'))
})
test('results distinguish actual accuracy and BKT estimates, preserving zero and missing values',()=>{
  const results={answered_questions:6,total_questions:6,correct_answers:3,accuracy:0.5,concepts:[
    {concept_id:1,concept_name:'Arrays',estimated_mastery:0,status:'weak'},
    {concept_id:2,concept_name:'Recursion',estimated_mastery:null,status:null},
  ]}
  const html=render(DiagnosticResultsView,{results,onDashboard(){},onProgress(){}})
  for(const text of ['Questions completed','Correct answers','Raw diagnostic accuracy','50.0%','BKT estimated mastery','0.0%','Not recorded','Dashboard Recommendations','My Progress'])assert.ok(html.includes(text))
  assert.ok(html.includes('not measured ability'))
  const empty=render(DiagnosticResultsView,{results:{...results,concepts:[]},onDashboard(){},onProgress(){}})
  assert.ok(empty.includes('No per-concept estimates'))
})
