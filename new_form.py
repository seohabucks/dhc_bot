from flask import Flask, render_template_string, request, send_file, session
from pyhwpx import Hwp
import os
import re

app = Flask(__name__)
app.secret_key = "dhc_stopper_secret"

# [함수들: num_to_kor, format_date_str, format_num은 이전과 동일]
def num_to_kor(num):
    if not num: return ""
    try:
        num = int(str(num).replace(',', ''))
        units = [''] + list('십백천')
        nums = list('일이삼사오육칠팔구')
        big_units = ['', '만', '억', '조']
        res = []
        out = []
        while num > 0:
            res.append(num % 10000)
            num //= 10000
        for i, r in enumerate(res):
            if r == 0: continue
            tmp = []
            for j, s in enumerate(str(r)[::-1]):
                if s != '0':
                    tmp.append(nums[int(s)-1] + units[j])
            if tmp:
                out.append("".join(tmp[::-1]) + big_units[i])
        return f"일금 {''.join(out[::-1])}원정"
    except: return ""

def format_date_str(date_str):
    if not date_str: return ""
    digits = re.sub(r'[^0-9]', '', str(date_str))
    if len(digits) == 8:
        return f"{digits[:4]}년 {int(digits[4:6])}월 {int(digits[6:])}일"
    return date_str

def format_num(num):
    try: return "{:,}".format(int(str(num).replace(',', '')))
    except: return num

HTML_LAYOUT = '''
<!DOCTYPE html>
<html>
<head>
    <title>계약서 자동화 시스템</title>
    <style>
        body { font-family: 'Malgun Gothic'; margin: 40px; background: #f4f7f9; color: #333; }
        .container { max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        h2 { border-bottom: 2px solid #007bff; padding-bottom: 10px; color: #007bff; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .full { grid-column: span 2; }
        label { font-weight: bold; font-size: 0.9em; display: block; margin-bottom: 5px; }
        input { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        input[readonly] { background: #f8f9fa; color: #555; border: 1px solid #ddd; }
        .btn-group { margin-top: 25px; display: flex; gap: 10px; }
        .btn { flex: 1; padding: 15px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; font-weight: bold; }
        .btn-primary { background: #007bff; color: white; }
        .btn-secondary { background: #6c757d; color: white; text-decoration: none; text-align: center; line-height: 1.2; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background: #f8f9fa; width: 35%; }
        
        body { font-family: 'Malgun Gothic'; margin: 40px; background: #f4f7f9; color: #333; }
        .container { max-width: 900px; margin: auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        
        /* 미리보기 계약서 스타일 */
        .preview-box { border: 2px solid #333; padding: 50px; line-height: 2; background: #fff; position: relative; }
        .preview-title { text-align: center; font-size: 24px; font-weight: bold; text-decoration: underline; margin-bottom: 40px; }
        .contract-item { margin-bottom: 15px; font-size: 16px; }
        
        /* 입력값 강조 스타일 (파란색 BOLD) */
        .highlight { color: #0047ab; font-weight: bold; border-bottom: 1px solid #0047ab; padding: 0 5px; }
        
        .btn-group { margin-top: 30px; display: flex; gap: 10px; }
        .btn { flex: 1; padding: 15px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; font-weight: bold; text-decoration: none; text-align: center; }
        .btn-primary { background: #007bff; color: white; }
        .btn-secondary { background: #6c757d; color: white; }
    </style>
    <script>
        function calculateAll() {
            // 1. 계약금액 읽기 (콤마 제거)
            let totalInput = document.getElementsByName('total_amount')[0].value.replace(/,/g, '');
            let total = parseInt(totalInput);

            if(!isNaN(total)) {
                // 2. 공급가액 계산 (합계 / 1.1)
                // Math.round를 사용하여 가장 가까운 만원 단위로 반올림합니다.
                // 430,650,000 / 1.1 = 391,500,000 딱 떨어지는 경우를 포함하여
                // 만원 단위로 가장 근접한 값을 찾습니다.
                let supply = Math.round((total / 1.1) / 10000) * 10000;
                
                // 3. 부가가치세는 전체 합계에서 공급가액을 뺀 나머지 (정산)
                let vat = total - supply;

                // 4. 이행보증금(10%) 및 하자보증금(3%) 계산
                let guarantee = Math.floor((total * 0.1));
                let repair = Math.floor((total * 0.03));

                // 화면 업데이트
                document.getElementsByName('supply_value')[0].value = supply.toLocaleString();
                document.getElementsByName('vat')[0].value = vat.toLocaleString();
                document.getElementsByName('guarantee_num')[0].value = guarantee.toLocaleString();
                document.getElementsByName('repair_amount_num')[0].value = repair.toLocaleString();
                
                // 입력창 콤마 정리
                document.getElementsByName('total_amount')[0].value = total.toLocaleString();
            }
        }
    </script>
</head>
<body>
    <div class="container">{{ content | safe }}</div>
</body>
</html>
'''

@app.route('/')
def index():
    form_html = '''
    <h2>1. 계약 정보 입력</h2>
    <form action="/preview" method="post">
        <div class="grid">
            <div class="full"><label>원도급사 이름 (파일명용)</label><input type="text" name="client_name" required></div>
            <div class="full"><label>발주자</label><input type="text" name="owner"></div>
            <div class="full"><label>공사장소</label><input type="text" name="location"></div>
            <div class="full"><label>도급공사명</label><input type="text" name="project_name"></div>
            <div class="full"><label>하도급공사명</label><input type="text" name="sub_project_name"></div>
            <div><label>착공일 (예: 20260401)</label><input type="text" name="start_date"></div>
            <div><label>준공일 (예: 20260731)</label><input type="text" name="end_date"></div>
            
            <hr class="full">
            
            <div><label style="color: #d9534f;">계약금액(총액) - 입력 후 탭/클릭</label>
                 <input type="text" name="total_amount" onchange="calculateAll()" placeholder="숫자만 입력"></div>
            <div><label>공급가액 (자동계산)</label><input type="text" name="supply_value" readonly></div>
            <div><label>부가가치세 (자동계산)</label><input type="text" name="vat" readonly></div>
            <div><label>노무비 (직접입력)</label><input type="text" name="labor_cost"></div>
            
            <div><label>이행보증금(10%) 자동계산</label><input type="text" name="guarantee_num" readonly></div>
            <div><label>하자보증금(3%) 자동계산</label><input type="text" name="repair_amount_num" readonly></div>
            
            <hr class="full">
            <div><label>원사업자 전화번호</label><input type="text" name="owner_contact"></div>
            <div><label>원사업자 주소</label><input type="text" name="owner_address"></div>
            <div><label>원사업자 대표이름</label><input type="text" name="owner_ceo"></div>
            <div><label>원사업자 사업자번호</label><input type="text" name="owner_reg_num"></div>
            
            <hr class="full">
            
            <div><label>계약일 (예: 20260413)</label><input type="text" name="contract_date"></div>
        </div>
        <div class="btn-group">
            <button type="submit" class="btn btn-primary">데이터 확인 및 미리보기</button>
        </div>
    </form>
    '''
    return render_template_string(HTML_LAYOUT, content=form_html)

# [이후 @app.route('/preview') 및 /save 로직은 이전과 동일하게 유지]
# 2. 미리보기(preview)
@app.route('/preview', methods=['POST'])
def preview():
    session['data'] = request.form
    d = request.form
    def hl(key, is_date=False, is_money=False):
        val = d.get(key, '')
        if is_date: val = format_date_str(val)
        if is_money: 
            num = int(val.replace(',', '')) if val else 0
            val = f"{num_to_kor(num)} (￦{format_num(num)})"
        return f'<span class="highlight">{val}</span>'

    # 양식 전문 형태의 미리보기
    preview_content = f'''
    <div class="preview-box">
        <div class="preview-title">건설업종 표준하도급계약서(표지)</div>
        <pre>
1. 발   주   자 : {hl('owner')}
  ㅇ 도급공사명 : {hl('project_name')}
  
2. 하도급공사명 : {hl('project_name')}중 {hl('sub_project_name')}

3. 공 사 장 소 : {hl('owner_address')}

4. 공 사 기 간 : 착공 {hl('start_date', True)}
                준공 {hl('end_date', True)}
                
5. 계 약 금 액 : {hl('total_amount', False, True)}
    ㅇ공급가액 : {hl('supply_value', False, True)}
      노 무 비 : {hl('labor_cost', False, True)}
      * 건설산업기본법 시행령 제84조 규정에 의한 노무비
    ㅇ부가가치세 : {hl('vat', False, True)}
   
6. 대금의 지급
  가. 선급금
  ㅇ 계약체결 후 ()일 이내에 일금   원정 (￦ )
  ※ 발주자로부터 선급금을 지급받은 날 또는 계약일로부터 15일 이내 그 내용과 비율에 따름
  
   나. 기성금
   (1) ()월 ()회
   (2) 목적물 인수일로부터 ( 60 )일 이내
   (3) 지급방법 : 현금 100%, 어음 %, 어음대체결제수단 %
  ※ 발주자로부터 지급받은 현금비율 이상 지급. 지급 받은 어음 등의 지급기간을 초과하지 않는 어음 등을 교부
  
  다. 설계변경, 경제상황변동 등에 따른 하도급대금 조정 및 지급 
   (1) 발주자로부터 조정 받은 날부터 30일 이내 그 내용과 비율에 따라 조정
   (2) 발주자로부터 지급받은 날부터 15일 이내 지급
   
   
7. 지급자재의 품목 및 수량 : 별도첨부

8. 계약이행보증금
 ㅇ 계약금액의 (10)%, {hl('guarantee_num', False, True)}
 
9. 하도급대금 지급보증금
 ㅇ 하도급거래 공정화에 관한 법률에 의함
 
10. 하자담보책임
  가. 하자보수보증금율 : 계약금액의 ( 3 )%
  나. 하자보수보증금 : {hl('repair_amount_num', False, True)}
  다. 하자담보책임기간 :  3 년
  
11. 지체상금요율 : 연 ( 0.05 )%

12. 지연이자율 : 연 ( )% (대금 지급·반환 지연) / 연 ( )% (손해배상 지연)

 ※ 하도급법령상 지급기일이 지난 경우에는 공정위 고시 지연이자율이 우선 적용

 양 당사자는 위 내용과 별첨 건설공사 표준하도급계약서(본문)에 따라 이 건설공사 하도급
 계약을 체결하고 계약서 2통을 작성하여 기명날인 후 각각 1통씩 보관한다.

<div style="text-align:center; margin-top:20px;">{hl('contract_date', True)}</div>
<br>
</pre>
<pre>
<h2>원사업자</h2>
상호 또는 명칭 : {hl('owner')}
전화번호 : {hl('owner_contact')}
주   소 : {hl('owner_address')}
대표자 성명 : {hl('owner_ceo')}   (인)
사업자번호 : {hl('owner_reg_num')}
</pre>
    </div>
    <div class="btn-group">
        <a href="/" class="btn btn-secondary">수정하기</a>
        <form action="/save" method="post" style="flex:1;"><button type="submit" class="btn btn-primary" style="width:100%;">HWPX 파일 저장</button></form>
    </div>
    '''
    return render_template_string(HTML_LAYOUT, content=preview_content)

@app.route('/save', methods=['POST'])
def save():
    data = session.get('data')
    if not data: return "세션 만료"
    hwp = Hwp(visible=False)
    try:
        template_path = os.path.join(os.getcwd(), "양식.hwp")
        hwp.open(template_path)
        
        # 1. 기본 텍스트 입력
        direct_fields = ["owner",
                         "project_name",
                         "sub_project_name",
                         "location",
                         "start_date",
                         "end_date",
                        #  계약금액
                         "total_amount",
                         "total_amount_kor",
                        #  공급가액
                         "supply_value",
                         "supply_value_kor",
                        #  노무비
                         "labor_cost",
                         "labor_cost_kor",
                        #  부가가치세
                         "vat",
                         "vat_kor",
                        #  계약이행보증금
                         "guarantee_num",
                         "guarantee_kor",
                        #  하자보증금
                         "repair_amount_num",
                         "repair_amount_kor",
                        #  계약일
                         "contract_date",
                        #  원사업자내용
                         "owner_contact",
                         "owner_address",
                         "owner_ceo",
                         "owner_reg_num"
                         ]
        for f in direct_fields:
            hwp.put_field_text(f, data.get(f, ""))
        
        for key, value in data.items():
            final_val = value
            if "_date" in key: final_val = format_date_str(value)
            hwp.put_field_text(key, final_val)
        total = int(data.get('total_amount', '0').replace(',', ''))
        # 숫자가 비어있거나 콤마가 포함된 경우를 대비한 안전한 변환 로직
        def safe_int(val):
            if not val: return 0
            # 콤마 제거 후 숫자만 남김
            clean_val = re.sub(r'[^0-9]', '', str(val))
            return int(clean_val) if clean_val else 0

        total = safe_int(data.get('total_amount'))
        
        money_map = {
            "total_amount": total,
            "supply_value": safe_int(data.get('supply_value')),
            "vat": safe_int(data.get('vat')),
            "labor_cost": safe_int(data.get('labor_cost')),  # 이제 비어있어도 0으로 처리됨
            "guarantee_num": safe_int(data.get('guarantee_num')),
            "repair_amount_num": safe_int(data.get('repair_amount_num'))
        }
        for field, val in money_map.items():
            hwp.put_field_text(field, format_num(val))
            kor_field = field.replace("_num", "") + "_kor"
            hwp.put_field_text(kor_field, num_to_kor(val))
        save_name = f"표준하도급계약서_{data.get('client_name')}.hwpx"
        save_path = os.path.join(os.getcwd(), save_name)
        hwp.save_as(save_path)
        return send_file(save_path, as_attachment=True)
    except Exception as e: return f"오류: {e}"
    finally: hwp.quit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)