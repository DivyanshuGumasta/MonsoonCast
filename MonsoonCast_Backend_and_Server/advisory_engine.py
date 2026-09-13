from __future__ import annotations
from dataclasses import dataclass
from typing import Any
BREAK_HIGH=0.5; BREAK_MODERATE=0.3; ONSET_HIGH=0.5; REVIVAL_HIGH=0.4; ACTIVE_HIGH=0.5
@dataclass
class Advisory:
    crop:str; lead_bucket:str; risk_level:str; action_key:str; text_en:str; text_hi:str; text_or:str
def _rules_for_crop(crop,probs):
    onset,active,break_,revival=probs.get('onset',0),probs.get('active',0),probs.get('break',0),probs.get('revival',0)
    if break_>=BREAK_HIGH:return Advisory(crop,'','high','delay_sowing_prepare_irrigation',f'High risk ({break_*100:.0f}%) of an extended dry spell ahead. Delay {crop} sowing if not yet sown; arrange irrigation/water storage for standing crop.',f'{crop} की बुवाई: आगे लंबे सूखे की {break_*100:.0f}% संभावना है। अभी बुवाई न करें और खड़ी फसल के लिए सिंचाई की व्यवस्था करें।',f'{crop} ପାଇଁ ସତର୍କତା: ଆଗାମୀ ଦିନରେ ଶୁଷ୍କ ଅବଧି ({break_*100:.0f}%) ର ସମ୍ଭାବନା। ବୁଣିବା ବିଳମ୍ବ କରନ୍ତୁ ଓ ଜଳସେଚନ ପ୍ରସ୍ତୁତ ରଖନ୍ତୁ।')
    if onset>=ONSET_HIGH and active>=ACTIVE_HIGH:return Advisory(crop,'','low','proceed_sowing',f'Monsoon onset with sustained rain likely ({onset*100:.0f}% onset, {active*100:.0f}% active). Conditions favorable to begin {crop} sowing.',f'मानसून की शुरुआत और लगातार बारिश की संभावना ({onset*100:.0f}%/{active*100:.0f}%)। {crop} की बुवाई शुरू करने के लिए स्थिति अनुकूल है।',f'ମୌସୁମୀ ପ୍ରାରମ୍ଭ ଓ ଲଗାତାର ବର୍ଷା ସମ୍ଭାବନା ({onset*100:.0f}%/{active*100:.0f}%)। {crop} ବୁଣିବା ପାଇଁ ଅନୁକୂଳ ଅବସ୍ଥା।')
    if revival>=REVIVAL_HIGH:return Advisory(crop,'','moderate','resume_after_break',f'Rain likely to revive after a dry spell ({revival*100:.0f}%). Resume field operations for {crop}; apply top-dressing fertilizer only after confirmed rain.',f'सूखे के बाद बारिश लौटने की {revival*100:.0f}% संभावना। {crop} के लिए खेत का काम फिर शुरू करें; बारिश की पुष्टि के बाद ही उर्वरक डालें।',f'ଶୁଷ୍କ ଅବଧି ପରେ ବର୍ଷା ଫେରିବାର {revival*100:.0f}% ସମ୍ଭାବନା। {crop} ପାଇଁ କ୍ଷେତ କାର୍ଯ୍ୟ ପୁନଃ ଆରମ୍ଭ କରନ୍ତୁ।')
    if break_>=BREAK_MODERATE:return Advisory(crop,'','moderate','watch_and_wait',f'Moderate dry-spell risk ({break_*100:.0f}%). Hold off on additional {crop} sowing; monitor soil moisture.',f'सूखे की मध्यम संभावना ({break_*100:.0f}%)। {crop} की अतिरिक्त बुवाई रोकें; मिट्टी की नमी पर नजर रखें।',f'ମଧ୍ୟମ ଶୁଷ୍କ ଅବଧି ସମ୍ଭାବନା ({break_*100:.0f}%)। {crop} ଅଧିକ ବୁଣିବା ବନ୍ଦ ରଖନ୍ତୁ; ମାଟିର ଆର୍ଦ୍ରତା ଉପରେ ନଜର ରଖନ୍ତୁ।')
    return Advisory(crop,'','low','normal_conditions',f'No major deviation expected for {crop}. Continue normal package of practices.',f'{crop} के लिए कोई बड़ा बदलाव अपेक्षित नहीं है। सामान्य खेती जारी रखें।',f'{crop} ପାଇଁ କୌଣସି ବଡ଼ ପରିବର୍ତ୍ତନ ଆଶା କରାଯାଉ ନାହିଁ। ସାଧାରଣ ଚାଷ ଜାରି ରଖନ୍ତୁ।')
DEFAULT_CROPS=['Rice','Cotton','Soybean','Pigeon pea (Arhar)']
def generate_advisories(outlook:dict[str,Any],crops:list[str]|None=None):
    crops=crops or DEFAULT_CROPS; out=[]
    for bucket in ['7d','14d','21d','30d']:
        probs=outlook.get(bucket)
        if not probs:continue
        for crop in crops:
            a=_rules_for_crop(crop,probs); a.lead_bucket=bucket
            out.append({'lead_bucket':bucket,'crop':crop,'risk_level':a.risk_level,'action_key':a.action_key,'text':{'en':a.text_en,'hi':a.text_hi,'or':a.text_or},'probabilities':probs})
    return out
