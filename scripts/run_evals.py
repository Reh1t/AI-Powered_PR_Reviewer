import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_agents.graph import pr_review_graph

async def run_evaluation():
    print("🚀 Starting Automated LLM Evaluation Pipeline...")
    
    with open('evals/test_cases.json', 'r') as f:
        test_cases = json.load(f)
        
    total_tests = len(test_cases)
    passed_tests = 0
    total_start_time = time.time()
    
    print(f"Loaded {total_tests} scenarios. Evaluating...\n")
    
    for idx, tc in enumerate(test_cases):
        print(f"[{idx+1}/{total_tests}] Running Scenario: {tc['name']} ({tc['id']})")
        
        initial_state = {
            "files_dict": {"app/test_file.py": tc['diff']},
            "rag_context": "No historical context needed for this eval.",
            "security_findings": [],
            "performance_findings": [],
            "style_findings": [],
            "final_findings": []
        }
        
        try:
            scenario_start_time = time.time()
            
            # Invoke LangGraph
            final_state = await pr_review_graph.ainvoke(initial_state)
            
            scenario_duration = time.time() - scenario_start_time
            
            findings = final_state.get("final_findings", [])
            
            # Tally categories
            sec_count = sum(1 for f in findings if f.agent_category == "Security")
            perf_count = sum(1 for f in findings if f.agent_category == "Performance")
            style_count = sum(1 for f in findings if f.agent_category == "Style")
            
            # Check assertions
            passed = True
            errors = []
            
            if sec_count < tc.get('expected_security_min', 0):
                passed = False
                errors.append(f"Expected >= {tc['expected_security_min']} Security findings, but got {sec_count}.")
            
            if perf_count < tc.get('expected_perf_min', 0):
                passed = False
                errors.append(f"Expected >= {tc['expected_perf_min']} Performance findings, but got {perf_count}.")
                
            if style_count < tc.get('expected_style_min', 0):
                passed = False
                errors.append(f"Expected >= {tc['expected_style_min']} Style findings, but got {style_count}.")
                
            # Max constraints (For false positives and constraints)
            if 'expected_security_max' in tc and sec_count > tc['expected_security_max']:
                passed = False
                errors.append(f"Expected <= {tc['expected_security_max']} Security findings, but got {sec_count}.")
                
            if 'expected_perf_max' in tc and perf_count > tc['expected_perf_max']:
                passed = False
                errors.append(f"Expected <= {tc['expected_perf_max']} Performance findings, but got {perf_count}.")
                
            if 'expected_style_max' in tc and style_count > tc['expected_style_max']:
                passed = False
                errors.append(f"Expected <= {tc['expected_style_max']} Style findings, but got {style_count}.")
                
            if passed:
                passed_tests += 1
                print(f"   ✅ PASS ({scenario_duration:.2f}s)")
            else:
                print(f"   ❌ FAIL ({scenario_duration:.2f}s): {', '.join(errors)}")
                print(f"      ↳ What the AI actually outputted:")
                if not findings:
                    print("         [Empty Array - The AI found zero issues]")
                for f in findings:
                    print(f"         - [{f.agent_category}] {f.vulnerability_type}: {f.suggested_fix_comment[:60]}...")
                
        except Exception as e:
            print(f"   ❌ ERROR: LangGraph crashed - {str(e)}")
            
    total_duration = time.time() - total_start_time
    avg_duration = total_duration / total_tests if total_tests > 0 else 0
    
    print("\n" + "="*40)
    print("📊 EVALUATION RESULTS")
    print("="*40)
    print(f"Total Scenarios: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Total Time: {total_duration:.2f}s")
    print(f"Avg Time Per Scenario: {avg_duration:.2f}s")
    
    score = (passed_tests / total_tests) * 100
    print(f"\nFinal Accuracy Score: {score:.1f}%")
    
    if score >= 90:
        print("🏆 GRADE: A (Production Ready)")
    elif score >= 75:
        print("🥈 GRADE: B (Good, but expect some false positives)")
    else:
        print("⚠️ GRADE: C (Needs prompt tuning or a larger model)")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
