from flask import Flask, render_template_string, request, send_file
from pyhwpx import Hwp
import os

app = Flask(__name__)

# 숫자를 한글 금액으로 변환하는 함수
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
        
        result = "".join(out[::-1])
        return f"일금{result}원정"
    except:
        return ""

# 숫자에 콤마 추가 함수
def format_num(num):
    try:
        return "{:,}".format(int(str(num).replace(',', '')))
    except:
        return num

HTML_FORM = '''
<!DOCTYPE html>
<html>
<head>
    <title>DHC Stopper 계약서 자동화</title>
    <style>
        body { font-family: 'Malgun Gothic'; margin: 40px; background: #f0f2f5; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 800px; margin: auto; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        label { font-weight: bold; display: block; margin-bottom: 5px; color: #333; }
        input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
        .btn { grid-column: span 2; background: #007bff; color: white; border: none; padding: 15px; border-radius: 8px; font-size: 18px; cursor: pointer; margin-top: 20px; }
        h2 { text-align: center; color: #007bff; }
    </style>
</head>
<body>
    <div class="card">
        <h2>표준하도급계약서 자동 생성</h2>
        <form action="/generate" method="post">
            <div class="grid">
                <div><label>원도급사 이름(파일명):</label><input type="text" name="client_name" placeholder="예: 백마종합건설"></div>
                <div><label>발주자:</label><input type="text" name="owner"></div>
                
                <div style="grid-column: span 2;"><label>도급공사명:</label><input type="text" name="project_name"></div>
                <div style="grid-column: span 2;"><label>하도급공사명:</label><input type="text" name="sub_project_name"></div>
                
                <div><label>착공일:</label><input type="text" name="start_date"> </div>
                <div><label>준공일:</label><input type="text" name="end_date"></div>
                
                <div><label>계약금액(총액):</label><input type="text" name="total_amount"></div>
                <div><label>공급가액:</label><input type="text" name="supply_value"></div>
                
                <div><label>노무비:</label><input type="text" name="labor_cost"></div>
                <div><label>부가가치세:</label><input type="text" name="vat"></div>
                
                <div><label>계약이행보증금:</label><input type="text" name="guarantee_num" readonly></div>
                <div><label>하자보증금:</label><input type="text" name="repair_amount_num" readonly></div>

                <div><label>원도급사 전화번호:</label><input type="text" name="owner_contact"></div>
                <div><label>원도급사 주소:</label><input type="text" name="owner_address"></div>
                <div><label>원도급사 대표:</label><input type="text" name="owner_ceo"></div>
                <div><label>원도급사 사업자번호:</label><input type="text" name="owner_reg_num"></div>

                <div style="grid-column: span 2;"><label>계약일:</label><input type="text" name="contract_date"></div>
            </div>
            <button type="submit" class="btn">한글(.hwpx) 파일 생성</button>
        </form>
    </div>
</body>
</html>
'''

@app.route('/')
def index(): return render_template_string(HTML_FORM)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.form
    hwp = Hwp(visible=False)
    
    try:
        # 양식 파일 로드
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

        # 2. 금액 계산 및 한글 변환 처리
        total = int(data.get('total_amount', 0).replace(',', ''))
        g_rate = float(data.get('guarantee_num', 10)) / 100
        r_rate = float(data.get('repair_amount_num', 3)) / 100

        money_data = {
            "total_amount": total,
            "supply_value": int(data.get('supply_value', 0).replace(',', '')),
            "labor_cost": int(data.get('labor_cost', 0).replace(',', '')),
            "vat": int(data.get('vat', 0).replace(',', '')),
            "guarantee_num": int(total * g_rate),
            "repair_amount_num": int(total * r_rate)
        }

        for field, val in money_data.items():
            # 숫자(콤마) 입력
            hwp.put_field_text(field if "num" in field else field, format_num(val))
            # 한글 금액 입력 (필드명_kor)
            kor_field = field.replace("_num", "") + "_kor"
            hwp.put_field_text(kor_field, num_to_kor(val))

        # 3. 파일 저장
        save_name = f"표준하도급계약서_{data.get('owner')}.hwpx"
        hwp.save_as(os.path.join(os.getcwd(), save_name))
        return f"<h3>생성 완료!</h3><p>파일명: {save_name}</p><a href='/'>돌아가기</a>"

    except Exception as e: return f"오류: {e}"
    finally: hwp.quit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)