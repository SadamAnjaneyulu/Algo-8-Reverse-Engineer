// Deterministic autonomous controller kernel. Canonical accounting is external;
// simulated fill accounting is reconciled against the received incremental fills.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace std;
template<class T> vector<T> readv(ifstream& f,size_t n){vector<T>x(n);f.read((char*)x.data(),n*sizeof(T));if(!f)throw runtime_error("truncated replay input");return x;}
struct Cycle {int id,u,split,T,C,base,step,expiry;vector<int>strike,right,minute,clock,session,phase,actual,observed;vector<double>feature,cash;vector<float>prior,open,pvol,vol,delta,vega,gamma;};
struct Config {int id,alloc,ex,gate,wing,reentry,final,ref,latency;double scale,budget,loss,capscale,partial;int shift;};
struct Calibration {double clock[2][2][18][4],pool[2][2][18][4],cap[2][3];};
struct Request {int t,j,signedq,closeonly,reason;};
struct Stats {double flow_minutes=0,flow_class_matches=0;uint64_t prediction_hash=1469598103934665603ULL;double loss_breach_minutes=0,max_loss=0,max_abs_vega=0;double pred[4]={},actual[4]={},match[4]={},exactq[4]={},exacttime[4]={},time1[4]={},qerror=0,qdenom=0,terr=0,near=0,inv_error=0,inv_denom=0,role_error=0,net_error=0,unmatched_minutes=0,obs_unmatched_minutes=0,minutes=0,final_target=0,final_match=0,final_error=0,unfilled=0,unfilled_qty=0,turnover=0,cost=0,realized=0,final_equity=NAN,missing_marks=0,negative_call_minutes=0,vega_breach_minutes=0,max_short=0,max_gross=0,directional_match=0;};
const int slots[18]={556,570,585,600,615,630,645,660,675,690,705,720,750,810,825,840,855,870};
int slot_index(int clock){for(int i=0;i<18;i++)if(slots[i]==clock)return i;return -1;}
int signof(int a){return(a>0)-(a<0);}bool good(double x){return isfinite(x)&&x>0;}

struct Replay {
 const Cycle& d;const Config& c;const Calibration& cal;
 vector<int>q,pred,reason;vector<double>cost,spotref,minprice;vector<int>born,lastcover,refired;vector<Request>queue;
 double cash=0,realized=0,side_realized[2]={},turnover=0,fees=0,carry_debit=NAN,session_start_equity=NAN;
 int previous_session=-1;bool ever_short=false,locked=false;double last_target[4]={},covered[4]={};
 vector<array<double,8>> path; // cash, realized, equity, delta, vega, gamma, turnover, costs
 vector<int>unfilled_by_time;double unfilledqty=0;
 Replay(const Cycle& data,const Config& cfg,const Calibration& k):d(data),c(cfg),cal(k),q(d.C),pred(d.T*d.C*4),reason(pred.size()),cost(d.C),spotref(d.C,NAN),minprice(d.C,INFINITY),born(d.C,-1),lastcover(2,-1000000),refired(2,1),path(d.T),unfilled_by_time(d.T){}
 int cell(int t,int j,int r)const{return(t*d.C+j)*4+r;}
 int total(int right,bool shorts)const {int out=0;for(int j=0;j<d.C;j++)if(d.right[j]==right)out+=shorts?max(-q[j],0):max(q[j],0);return out;}
 int totalshort()const{return total(0,true)+total(1,true);}
 double reference(int t)const {
  double x=d.feature[t*8];if(c.ref==0||!isfinite(x))return x;vector<double>a;
  for(int k=max(0,t-2);k<=t;k++)if(d.session[k]==d.session[t]&&isfinite(d.feature[k*8]))a.push_back(d.feature[k*8]);
  if(a.empty())return NAN;sort(a.begin(),a.end());return a[a.size()/2];
 }
 void fill(int t,int j,int signedq,int closeonly,int why,double supplied_price=NAN){
  if(closeonly){if(signedq*q[j]>=0)return;signedq=signof(signedq)*min(abs(signedq),abs(q[j]));}
  if(!signedq)return;double price=isfinite(supplied_price)?supplied_price:d.open[t*d.C+j];
  if(!good(price)){unfilled_by_time[t]++;unfilledqty+=abs(signedq);return;}
  int old=q[j],closing=old*signedq<0?min(abs(old),abs(signedq)):0,opening=abs(signedq)-closing;
  double rp=closing*(price-cost[j])*signof(old);realized+=rp;side_realized[d.right[j]]+=rp;
  int residual=old+signof(signedq)*closing;
  if(opening){cost[j]=(abs(residual)*cost[j]+opening*price)/(abs(residual)+opening);if(!old||signof(old)!=signof(old+signedq)){spotref[j]=reference(t);born[j]=t;minprice[j]=price;}}
  if(closing){int r=signedq>0?1:3;pred[cell(t,j,r)]+=closing;reason[cell(t,j,r)]|=why;covered[d.right[j]+(signedq<0?2:0)]+=closing/double(d.base);
   if(signedq>0){lastcover[d.right[j]]=t;refired[d.right[j]]=0;}}
  if(opening){int r=signedq<0?0:2;pred[cell(t,j,r)]+=opening;reason[cell(t,j,r)]|=why;}
  q[j]+=signedq;if(!q[j]){cost[j]=0;born[j]=-1;minprice[j]=INFINITY;}
  cash-=signedq*price;turnover+=abs(signedq)*price;fees+=.0025*abs(signedq)*price+20*ceil(abs(signedq)/double(d.base))+.05*abs(signedq);
 }
 void request(int t,int j,int signedq,int closeonly,int why){if(!signedq)return;int when=t+c.latency;if(when>=d.T||d.session[when]!=d.session[t]){unfilled_by_time[t]++;unfilledqty+=abs(signedq);return;}if(c.latency==0)fill(t,j,signedq,closeonly,why);else queue.push_back({when,j,signedq,closeonly,why});}
 void close_side(int t,int right,int quantity,int why){
  int before=total(right,true);int remaining=quantity;
  for(int j=0;j<d.C&&remaining>0;j++)if(d.right[j]==right&&q[j]<0){int amount=min(-q[j],remaining);request(t,j,amount,1,why);remaining-=amount;}
  // Separate protection-removal requests, proportional to requested short reduction.
  int wing=before?int(round(total(right,false)*min(quantity,before)/double(before)/d.base))*d.base:0;
  for(int j=0;j<d.C&&wing>0;j++)if(d.right[j]==right&&q[j]>0){int amount=min(q[j],wing);request(t,j,-amount,1,why);wing-=amount;}
 }
 void liquidate(int t,int why){for(int j=0;j<d.C;j++)if(q[j]<0)request(t,j,-q[j],1,why);for(int j=0;j<d.C;j++)if(q[j]>0)request(t,j,-q[j],1,why);}
 int atm(int t,int right)const {double spot=reference(t);if(!good(spot))return -1;int strike=int(floor(spot/d.step+.5))*d.step;for(int j=0;j<d.C;j++)if(d.strike[j]==strike&&d.right[j]==right&&good(d.prior[t*d.C+j])&&d.pvol[t*d.C+j]>0)return j;return -1;}
 int wing(int t,int shortj,bool initial)const {
  int right=d.right[shortj],at=d.strike[shortj];bool fixed=c.wing==2||(initial&&(c.wing==0||c.wing==3));
  int distance=d.u==0?2000:(d.expiry>=20260916?2000:4000);
  int target=at+(right==0?distance:-distance);double budget=d.prior[t*d.C+shortj]*c.budget;
  if(d.u==1&& !fixed)budget=d.phase[t]?floor(budget*10)/10:round(budget*10)/10;
  int best=-1;double bestscore=INFINITY;
  for(int j=0;j<d.C;j++){
   if(d.right[j]!=right||(right==0?d.strike[j]<=at:d.strike[j]>=at))continue;
   float p=d.prior[t*d.C+j];if(!good(p)||!(d.pvol[t*d.C+j]>0))continue;
   if(fixed){if(d.strike[j]==target)return j;continue;}
   // SENSEX expiry nearest-premium, other cohorts ceiling selector.
   if(!(d.u==1&&d.phase[t])&&p>budget+1e-6)continue;
   double score=(d.u==1&&d.phase[t])?abs(p-budget):budget-p;
   if(score<bestscore-1e-6||(abs(score-bestscore)<=1e-6&&(best<0||abs(d.strike[j]-at)<abs(d.strike[best]-at)))){best=j;bestscore=score;}
  }return best;
 }
 bool gate(int t,bool opening)const {if(c.gate==0)return true;double x=d.feature[t*8+(c.gate==1?(opening?4:2):(opening?5:3))];return isfinite(x)&&x<=(c.gate==1?.35:.70);}
 void allocation(int t,int slot,bool extra,int onlyright=-1){
  bool opening=slot==0&&!extra; if(locked||!gate(t,opening))return;
  if(!extra&&d.phase[t]&&slot>0&&!totalshort())return;
  double add[4]={};
  for(int r=0;r<4;r++){
   double weight=extra?1:(c.alloc==1?cal.pool[d.u][d.phase[t]][slot][r]:cal.clock[d.u][d.phase[t]][slot][r]);
   if(!extra&&c.alloc==2)weight=opening?3:1;
   int right=r%2;bool sh=r<2;double current=total(right,sh)/double(d.base);
   if(!extra&&c.alloc==3){last_target[r]+=weight;weight=max(last_target[r]-current,0.);}
   if(!extra&&c.alloc==4)weight=opening?3:covered[r];
   if(!extra&&c.alloc==5){double iv=d.feature[t*8+6];if(!good(iv)){weight=0;}else{weight*=clamp(cal.cap[d.u][2]/iv,.5,1.5);if(sh)weight=min(weight,max(cal.cap[d.u][0]-current,0.));}}
   add[r]=max(0.,round(weight*c.scale));
  }
  for(int right=0;right<2;right++){
   if(onlyright>=0&&right!=onlyright)continue;
   int wait=c.reentry==1?5:c.reentry==2?15:0;if(t-lastcover[right]<wait)continue;
   int shortj=atm(t,right);if(shortj<0){if(add[right]>0)unfilled_by_time[t]++;continue;}
   int longj=wing(t,shortj,opening&&!ever_short);if(longj<0){if(add[right]>0||add[right+2]>0)unfilled_by_time[t]++;continue;}
   if(c.alloc==5){double v=0;bool valid=true;for(int j=0;j<d.C;j++)if(q[j]){if(!isfinite(d.vega[t*d.C+j]))valid=false;else v+=q[j]*d.vega[t*d.C+j];}if(!valid||abs(v)>cal.cap[d.u][1])continue;}
   int why=extra?8:1;
   request(t,longj,int(add[right+2])*d.base,0,why);request(t,shortj,-int(add[right])*d.base,0,why);
  }
  if(!extra)for(int r=0;r<4;r++)covered[r]=0;
 }
 array<double,4> mark(int t)const {double value=cash,delta=0,vega=0,gamma=0;bool ok=true,risk=true;
  for(int j=0;j<d.C;j++)if(q[j]){float p=d.prior[t*d.C+j];if(!good(p))ok=false;else value+=q[j]*p;if(!isfinite(d.delta[t*d.C+j])||!isfinite(d.vega[t*d.C+j])||!isfinite(d.gamma[t*d.C+j]))risk=false;else{delta+=q[j]*d.delta[t*d.C+j];vega+=q[j]*d.vega[t*d.C+j];gamma+=q[j]*d.gamma[t*d.C+j];}}
  return {ok?value:NAN,risk?delta:NAN,risk?vega:NAN,risk?gamma:NAN};
 }
 void run(){
  for(int t=0;t<d.T;t++){
   for(size_t k=0;k<queue.size();){if(queue[k].t==t){auto a=queue[k];fill(t,a.j,a.signedq,a.closeonly,a.reason);queue.erase(queue.begin()+k);}else k++;}
   if(d.session[t]!=previous_session){
    if(previous_session>=0){carry_debit=0;bool valid=true;for(int j=0;j<d.C;j++)if(q[j]<0){float p=d.prior[(t-1)*d.C+j];if(!good(p))valid=false;else carry_debit-=q[j]*p;}if(!valid)carry_debit=NAN;}
    previous_session=d.session[t];for(int r=0;r<4;r++){last_target[r]=0;covered[r]=0;}session_start_equity=mark(t)[0];
   }
   int deadline=(c.final==1&&d.expiry<20260803?927:914)+c.shift;
   bool finish=d.phase[t]&&d.clock[t]>=deadline;
   if(finish)liquidate(t,16);
   else{
    auto before=mark(t);double side[2]={side_realized[0],side_realized[1]};bool sideok[2]={true,true};
    for(int j=0;j<d.C;j++)if(q[j]){float p=d.prior[t*d.C+j];if(!good(p))sideok[d.right[j]]=false;else side[d.right[j]]+=q[j]*(p-cost[j]);}
    bool allstop=(c.ex==9||c.ex==11)&&d.phase[t]&&isfinite(before[0])&&before[0]<=-200000*c.capscale;
    if(c.ex==10&&d.phase[t]&&good(carry_debit)&&isfinite(before[0])){
     // Explicit candidate: loss from previous session's final *marked* equity.
     double start=path[t>0?t-1:0][2];int z=t;while(z>0&&d.session[z-1]==d.session[t])z--;if(z>0)start=path[z-1][2];
     allstop=isfinite(start)&&before[0]-start<=-.04*carry_debit*c.capscale;
    }
    if(allstop){liquidate(t,4);locked=true;}
    else {
     if(c.ex==8)for(int right=0;right<2;right++)if(sideok[right]&&side[right]<=-100000*c.capscale)close_side(t,right,total(right,true),2);
     for(int j=0;j<d.C;j++)if(q[j]<0){float p=d.prior[t*d.C+j];if(!good(p)||!good(cost[j]))continue;minprice[j]=min(minprice[j],double(p));bool exit=false;
      double loss=c.loss>0?c.loss:(c.ex==1?.30:c.ex==2||c.ex==11?.50:.75);
      if(c.ex==1||c.ex==2||c.ex==3||c.ex==11)exit=p>=cost[j]*(1+loss);
      if(c.ex==4)exit=p<=cost[j]*.10;
      if(c.ex==5)exit=minprice[j]<=cost[j]*.5&&p-minprice[j]>=cost[j]*.20;
      if(c.ex==6||c.ex==7){double s=reference(t);double move=(s/spotref[j]-1)*(d.right[j]==0?1:-1);exit=isfinite(move)&&move>=(c.ex==6?.003:.005);}
      if(exit){int amount=max(d.base,int(round((-q[j])*c.partial/d.base))*d.base);int right=d.right[j];
       int before_short=total(right,true),wingqty=before_short?int(round(total(right,false)*min(amount,-q[j])/double(before_short)/d.base))*d.base:0;
       request(t,j,min(amount,-q[j]),1,2);
       for(int k=0;k<d.C&&wingqty>0;k++)if(d.right[k]==right&&q[k]>0){int a=min(q[k],wingqty);request(t,k,-a,1,2);wingqty-=a;}
      }
     }
     if(c.wing==3)for(int j=0;j<d.C;j++)if(q[j]>0&&t-born[j]>=15&&good(d.prior[t*d.C+j])&&d.prior[t*d.C+j]<.25*cost[j]){
      int a=atm(t,d.right[j]);if(a<0)continue;int target=wing(t,a,false);if(target<0||target==j)continue;int amount=q[j];request(t,target,amount,0,32);request(t,j,-amount,1,32);
     }
    }
    if(c.reentry==3&&ever_short&&totalshort()==0)locked=true;
    int slot=slot_index(d.clock[t]);if(slot>=0)allocation(t,slot,false);
    if(c.reentry==1||c.reentry==2)for(int right=0;right<2;right++)if(!refired[right]&&t-lastcover[right]>=(c.reentry==1?5:15)&&d.session[t]==d.session[max(lastcover[right],0)]){allocation(t,0,true,right);refired[right]=1;}
   }
   if(totalshort()>0)ever_short=true;
   auto state=mark(t);path[t]={cash,realized,state[0],state[1],state[2],state[3],turnover,fees};
  }
 }
};

void score(Replay&r,int phase,Stats&s){const Cycle&d=r.d;
 vector<array<int,4>>p,a; // t,j,role,q
 int lastobs=-1,lastsim=-1;bool prevobs=false,prevsim=false;
 vector<int>sim(d.C);int prev_unfilled=0;
 for(int t=0;t<d.T;t++){
  for(int j=0;j<d.C;j++)sim[j]+=-r.pred[r.cell(t,j,0)]+r.pred[r.cell(t,j,1)]+r.pred[r.cell(t,j,2)]-r.pred[r.cell(t,j,3)];
  int osh=0,ssh=0;for(int j=0;j<d.C;j++){osh+=max(-d.observed[t*d.C+j],0);ssh+=max(-sim[j],0);}
  if(prevobs&&osh==0)lastobs=t;if(prevsim&&ssh==0)lastsim=t;prevobs=osh>0;prevsim=ssh>0;
  if(phase<2&&d.phase[t]!=phase)continue;
  s.minutes++;s.unfilled+=r.unfilled_by_time[t];
  int predicted_open=0,predicted_close=0,actual_open=0,actual_close=0;
  double roleobs[4]={},rolesim[4]={};double netobs[2]={},netsim[2]={};
  for(int j=0;j<d.C;j++){
   int observed=d.observed[t*d.C+j];s.inv_error+=abs(sim[j]-observed)/double(d.base);s.inv_denom+=(abs(sim[j])+abs(observed))/double(d.base);
   roleobs[(observed>0?2:0)+d.right[j]]+=abs(observed)/double(d.base);rolesim[(sim[j]>0?2:0)+d.right[j]]+=abs(sim[j])/double(d.base);
   netobs[d.right[j]]+=observed/double(d.base);netsim[d.right[j]]+=sim[j]/double(d.base);
   for(int k=0;k<4;k++){
    int x=r.pred[r.cell(t,j,k)],y=d.actual[r.cell(t,j,k)];
    if(k==0||k==2){predicted_open+=x;actual_open+=y;}else{predicted_close+=x;actual_close+=y;}
    if(x){for(uint64_t value:{uint64_t(d.minute[t]),uint64_t(j),uint64_t(k),uint64_t(x)}){s.prediction_hash^=value;s.prediction_hash*=1099511628211ULL;}s.pred[k]++;s.qdenom+=x/double(d.base);p.push_back({t,j,k,x});}
    if(y){s.actual[k]++;s.qdenom+=y/double(d.base);a.push_back({t,j,k,y});}
   }
  }
  auto flowclass=[](int op,int cl){return op&&cl?3:op?1:cl?2:0;};int pc=flowclass(predicted_open,predicted_close),ac=flowclass(actual_open,actual_close);if(pc||ac){s.flow_minutes++;s.flow_class_matches+=pc==ac;}
  for(int k=0;k<4;k++)s.role_error+=abs(roleobs[k]-rolesim[k]);for(int k=0;k<2;k++)s.net_error+=abs(netobs[k]-netsim[k]);
  if(rolesim[2]!=rolesim[0]||rolesim[3]!=rolesim[1])s.unmatched_minutes++;
  if(roleobs[2]!=roleobs[0]||roleobs[3]!=roleobs[1])s.obs_unmatched_minutes++;
  if(rolesim[0]>rolesim[2])s.negative_call_minutes++;
  if(isfinite(r.path[t][4])&&abs(r.path[t][4])>r.cal.cap[d.u][1])s.vega_breach_minutes++;
  s.max_short=max(s.max_short,rolesim[0]+rolesim[1]);s.max_gross=max(s.max_gross,accumulate(rolesim,rolesim+4,0.));
  if(!isfinite(r.path[t][2]))s.missing_marks++;else{s.max_loss=max(s.max_loss,-r.path[t][2]);if(d.phase[t]&&r.path[t][2]<-200000*r.c.capscale)s.loss_breach_minutes++;}
  if(isfinite(r.path[t][4]))s.max_abs_vega=max(s.max_abs_vega,abs(r.path[t][4]));
 }
 // Maximum-cardinality chronological matching for identical contract/action.
 vector<char>used(a.size());double matchedqty=0;
 vector<vector<int>> bygroup(d.C*4);for(size_t i=0;i<a.size();i++)bygroup[a[i][1]*4+a[i][2]].push_back(i);
 vector<size_t>cursor(d.C*4);
 for(auto x:p){int g=x[1]*4+x[2];auto&group=bygroup[g];auto&where=cursor[g];
  while(where<group.size()&&d.minute[a[group[where]][0]]<d.minute[x[0]]-2)where++;
  if(where<group.size()&&d.minute[a[group[where]][0]]<=d.minute[x[0]]+2){int i=group[where++];auto y=a[i];used[i]=1;int role=x[2];double error=abs(d.minute[x[0]]-d.minute[y[0]]);s.match[role]++;s.exactq[role]+=x[3]==y[3];s.exacttime[role]+=error==0;s.time1[role]+=error<=1;s.terr+=error;matchedqty+=2*min(x[3],y[3])/double(d.base);}
 }
 // Recompute exact/one-minute match counts independently, not subsets of +/-2.
 fill(s.exacttime,s.exacttime+4,0);fill(s.time1,s.time1+4,0);
 for(int tol=0;tol<=1;tol++){fill(cursor.begin(),cursor.end(),0);for(auto x:p){int g=x[1]*4+x[2];auto&group=bygroup[g];auto&where=cursor[g];while(where<group.size()&&d.minute[a[group[where]][0]]<d.minute[x[0]]-tol)where++;if(where<group.size()&&d.minute[a[group[where]][0]]<=d.minute[x[0]]+tol){where++;if(tol==0)s.exacttime[x[2]]++;else s.time1[x[2]]++;}}}
 s.qerror=s.qdenom-matchedqty;
 fill(used.begin(),used.end(),0);
 // A separately labeled near-strike diagnostic, not the primary exact match.
 size_t left=0;
 for(auto x:p){int best=-1,bestdist=999999;while(left<a.size()&&d.minute[a[left][0]]<d.minute[x[0]]-2)left++;
  for(size_t i=left;i<a.size()&&d.minute[a[i][0]]<=d.minute[x[0]]+2;i++)if(!used[i]&&a[i][2]==x[2]&&d.right[a[i][1]]==d.right[x[1]]){int dist=abs(d.strike[a[i][1]]-d.strike[x[1]]);if(dist<=d.step&&dist<bestdist){best=i;bestdist=dist;}}if(best>=0){used[best]=1;s.near++;}}

 vector<vector<int>> directiongroups(8);for(size_t i=0;i<a.size();i++)directiongroups[d.right[a[i][1]]*4+a[i][2]].push_back(i);vector<size_t>dcursor(8);
 for(auto x:p){int group=d.right[x[1]]*4+x[2];auto& choices=directiongroups[group];auto& cursor=dcursor[group];while(cursor<choices.size()&&d.minute[a[choices[cursor]][0]]<d.minute[x[0]]-2)cursor++;if(cursor<choices.size()&&d.minute[a[choices[cursor]][0]]<=d.minute[x[0]]+2){cursor++;s.directional_match++;}}
 if(phase==2||phase==1){bool unresolved=prevobs;if(!unresolved&&lastobs>=0){s.final_target=1;if(!prevsim&&lastsim>=0){s.final_error=abs(d.minute[lastsim]-d.minute[lastobs]);s.final_match=s.final_error<=2;}else s.final_error=9999;}}
 int last=d.T-1; // Economics for whole cycle only, never a selection input.
 if(phase==2){s.realized=r.realized;s.final_equity=r.path[last][2];s.turnover=r.turnover;s.cost=r.fees;s.unfilled_qty=r.unfilledqty;}
}

void header(ostream&f){f<<"candidate_id,cycle_id,index,split,phase,minutes";for(string x:{"pred","actual","match","exactq","exacttime","time1"})for(int r=0;r<4;r++)f<<","<<x<<r;f<<",qerror,qdenom,timing_abs_minutes,near_strike_matches,inventory_error,inventory_denom,role_error,net_error,unmatched_minutes,observed_unmatched_minutes,final_target,final_match,final_error,unfilled_requests,unfilled_quantity,turnover,cost,realized,final_equity,missing_marks,negative_call_minutes,vega_breach_minutes,max_short_base_units,max_gross_base_units,prediction_hash,loss_breach_minutes,max_loss,max_abs_vega,directional_matches,flow_minutes,flow_class_matches\n";}
void output(ostream&f,const Replay&r,int ph,const Stats&s){f<<r.c.id<<","<<r.d.id<<","<<r.d.u<<","<<r.d.split<<","<<ph<<","<<s.minutes;for(auto ptr:{s.pred,s.actual,s.match,s.exactq,s.exacttime,s.time1})for(int k=0;k<4;k++)f<<","<<ptr[k];f<<","<<s.qerror<<","<<s.qdenom<<","<<s.terr<<","<<s.near<<","<<s.inv_error<<","<<s.inv_denom<<","<<s.role_error<<","<<s.net_error<<","<<s.unmatched_minutes<<","<<s.obs_unmatched_minutes<<","<<s.final_target<<","<<s.final_match<<","<<s.final_error<<","<<s.unfilled<<","<<s.unfilled_qty<<","<<s.turnover<<","<<s.cost<<","<<s.realized<<","<<s.final_equity<<","<<s.missing_marks<<","<<s.negative_call_minutes<<","<<s.vega_breach_minutes<<","<<s.max_short<<","<<s.max_gross<<","<<s.prediction_hash<<","<<s.loss_breach_minutes<<","<<s.max_loss<<","<<s.max_abs_vega<<","<<s.directional_match<<","<<s.flow_minutes<<","<<s.flow_class_matches<<"\n";}
void trace(const Replay&r,ostream&actions,ostream&inventory){const Cycle&d=r.d;vector<int>q(d.C);for(int t=0;t<d.T;t++){
 for(int j=0;j<d.C;j++)for(int k=0;k<4;k++){int x=r.pred[r.cell(t,j,k)];if(x)actions<<r.c.id<<","<<d.id<<","<<d.minute[t]<<","<<d.strike[j]<<","<<d.right[j]<<","<<k<<","<<x<<","<<r.reason[r.cell(t,j,k)]<<","<<d.open[t*d.C+j]<<","<<d.vol[t*d.C+j]<<","<<d.prior[t*d.C+j]<<"\n";q[j]+=k==0||k==3?-x:x;}
 inventory<<r.c.id<<","<<d.id<<","<<d.minute[t]<<","<<r.path[t][0]<<","<<r.path[t][1]<<","<<r.path[t][2]<<","<<r.path[t][3]<<","<<r.path[t][4]<<","<<r.path[t][5]<<","<<r.path[t][6]<<","<<r.path[t][7]<<",\"[";bool comma=false;for(int j=0;j<d.C;j++)if(q[j]){if(comma)inventory<<";";inventory<<d.strike[j]<<":"<<d.right[j]<<":"<<q[j];comma=true;}inventory<<"]\",\"[";comma=false;for(int j=0;j<d.C;j++)if(d.observed[t*d.C+j]){if(comma)inventory<<";";inventory<<d.strike[j]<<":"<<d.right[j]<<":"<<d.observed[t*d.C+j];comma=true;}inventory<<"]\"\n";
}}
int main(int argc,char**argv){try{
 if(argc<4)throw runtime_error("usage: replay INPUT CONFIGS CALIBRATION [trace-prefix]");
 ifstream f(argv[1],ios::binary);auto prefix=readv<int>(f,2);if(prefix[0]!=80301)throw runtime_error("wrong binary schema");vector<Cycle>cycles;
 for(int k=0;k<prefix[1];k++){auto z=readv<int>(f,8);Cycle d;d.id=z[0];d.u=z[1];d.split=z[2];d.T=z[3];d.C=z[4];d.base=z[5];d.step=z[6];d.expiry=z[7];d.strike=readv<int>(f,d.C);d.right=readv<int>(f,d.C);d.minute=readv<int>(f,d.T);d.clock=readv<int>(f,d.T);d.session=readv<int>(f,d.T);d.phase=readv<int>(f,d.T);d.feature=readv<double>(f,d.T*8);d.prior=readv<float>(f,d.T*d.C);d.open=readv<float>(f,d.T*d.C);d.pvol=readv<float>(f,d.T*d.C);d.vol=readv<float>(f,d.T*d.C);d.delta=readv<float>(f,d.T*d.C);d.vega=readv<float>(f,d.T*d.C);d.gamma=readv<float>(f,d.T*d.C);d.actual=readv<int>(f,d.T*d.C*4);d.observed=readv<int>(f,d.T*d.C);d.cash=readv<double>(f,d.T);cycles.push_back(move(d));}
 ifstream cf(argv[2]);string line;vector<Config>configs;while(getline(cf,line)){if(line.empty()||line[0]=='#')continue;replace(line.begin(),line.end(),',',' ');istringstream s(line);Config c;s>>c.id>>c.alloc>>c.ex>>c.gate>>c.wing>>c.reentry>>c.final>>c.ref>>c.latency>>c.scale>>c.budget>>c.loss>>c.capscale>>c.partial>>c.shift;if(!s)throw runtime_error("invalid config");configs.push_back(c);}
 Calibration cal;ifstream kf(argv[3]);for(int u=0;u<2;u++)for(int ph=0;ph<2;ph++)for(int slot=0;slot<18;slot++)for(int r=0;r<4;r++)kf>>cal.clock[u][ph][slot][r];for(int u=0;u<2;u++)for(int ph=0;ph<2;ph++)for(int slot=0;slot<18;slot++)for(int r=0;r<4;r++)kf>>cal.pool[u][ph][slot][r];for(int u=0;u<2;u++)for(int j=0;j<3;j++)kf>>cal.cap[u][j];if(!kf)throw runtime_error("invalid calibration");
 if(argc>4&&string(argv[4])=="--audit-observed"){
  if(argc<6)throw runtime_error("reference fills file required");ifstream rf(argv[5],ios::binary);int n=readv<int>(rf,1)[0];
  struct Reference{int cid,t,j,q;double price;};vector<Reference> refs;
  for(int i=0;i<n;i++){auto a=readv<int>(rf,4);auto b=readv<double>(rf,1);refs.push_back({a[0],a[1],a[2],a[3],b[0]});}
  cout<<"cycle_id,minute_quantity_checks,maximum_cash_error,final_realized,final_cash\n";
  for(auto&d:cycles){Replay r(d,configs[0],cal);vector<Reference> fs;for(auto&a:refs)if(a.cid==d.id)fs.push_back(a);size_t pos=0;double maxerror=0;
   for(int t=0;t<d.T;t++){while(pos<fs.size()&&fs[pos].t==t){auto a=fs[pos++];r.fill(t,a.j,a.q,0,64,a.price);}for(int j=0;j<d.C;j++)if(r.q[j]!=d.observed[t*d.C+j])throw runtime_error("canonical position mismatch");maxerror=max(maxerror,abs(r.cash-d.cash[t]));}
   if(maxerror>1e-5)throw runtime_error("canonical cash mismatch");cout<<setprecision(14)<<d.id<<","<<d.T<<","<<maxerror<<","<<r.realized<<","<<r.cash<<"\n";
  }return 0;
 }
 if(argc>4&&string(argv[4]).rfind("--until=",0)==0){int until=stoi(string(argv[4]).substr(8));cycles.erase(remove_if(cycles.begin(),cycles.end(),[until](const Cycle&d){return d.expiry>until;}),cycles.end());}
 bool tracing=argc>4&&string(argv[4]).rfind("--",0)!=0;
 ofstream ta,ti;if(tracing){ta.open(string(argv[4])+"_actions.csv");ti.open(string(argv[4])+"_inventory.csv");ta<<"candidate_id,cycle_id,minute,strike,right,action,quantity,reason_mask,fill_price,execution_bar_volume,preceding_premium\n";ti<<"candidate_id,cycle_id,minute,cash,realized,marked_equity,delta,vega,gamma,turnover,cost,simulated_book,observed_book\n";ta<<setprecision(12);ti<<setprecision(12);}
 cout<<setprecision(12);header(cout);int n=0;
 for(auto&c:configs){for(auto&d:cycles){Replay r(d,c,cal);r.run();for(int ph=0;ph<3;ph++){if(ph<2&&count(d.phase.begin(),d.phase.end(),ph)==0)continue;Stats s;score(r,ph,s);output(cout,r,ph,s);}if(tracing)trace(r,ta,ti);}if(++n%100==0)cerr<<"Replayed "<<n<<"/"<<configs.size()<<" controllers\n";}
 }catch(exception&e){cerr<<e.what()<<"\n";return 1;}return 0;}
