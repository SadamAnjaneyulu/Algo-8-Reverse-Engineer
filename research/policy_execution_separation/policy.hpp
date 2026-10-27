// Desired inventory policy: does not read execution configuration, queues or
// historical action/position labels. Confirmed fills are feedback.
struct DesiredPolicy {
 const Cycle& d;const Calibration& cal;int allocation,risk;
 vector<int>target;double cumulative[4]={},episode[2]={};bool side_locked[2]={};int blocked[2]={-1,-1};
 bool initialized=false,locked=false;int session=-1,version=0,reason=0;
 DesiredPolicy(const Cycle&data,const Calibration&k,int a,int r):d(data),cal(k),allocation(a),risk(r),target(d.C){}
 int find(int strike,int right)const{for(int j=0;j<d.C;j++)if(d.strike[j]==strike&&d.right[j]==right)return j;return -1;}
 int total(int right,bool shortside)const{int n=0;for(int j=0;j<d.C;j++)if(d.right[j]==right)n+=shortside?max(-target[j],0):max(target[j],0);return n;}
 int atm(int t,int right)const{double spot=d.feature[t*8];if(!good(spot))return -1;return find(int(floor(spot/d.step+.5))*d.step,right);}
 int budgetwing(int t,int s)const{
  if(s<0||!good(d.prior[t*d.C+s]))return -1;double budget=.025*d.prior[t*d.C+s];if(d.u==1)budget=d.phase[t]?floor(budget*10)/10:round(budget*10)/10;
  int best=-1;double error=INFINITY;
  for(int j=0;j<d.C;j++)if(d.right[j]==d.right[s]&&(d.right[s]==0?d.strike[j]>d.strike[s]:d.strike[j]<d.strike[s])){
   double p=d.prior[t*d.C+j];if(!good(p)||!(d.pvol[t*d.C+j]>0))continue;
   bool nearest=d.u==1&&d.phase[t];if(!nearest&&p>budget+1e-6)continue;double e=nearest?abs(p-budget):budget-p;
   if(e<error-1e-6||(abs(e-error)<=1e-6&&(best<0||abs(d.strike[j]-d.strike[s])<abs(d.strike[best]-d.strike[s])))){best=j;error=e;}
  }return best;
 }
 void reduce_longs(int right,int quantity){for(int j=0;j<d.C&&quantity>0;j++)if(d.right[j]==right&&target[j]>0){int q=min(target[j],quantity);target[j]-=q;quantity-=q;}}
 void reduce_shorts(int right,int quantity){for(int j=0;j<d.C&&quantity>0;j++)if(d.right[j]==right&&target[j]<0){int q=min(-target[j],quantity);target[j]+=q;quantity-=q;}}
 bool update(int t,const vector<int>&confirmed,const vector<double>&cost,const double*realized){
  auto previous=target;reason=0;
  if(session!=d.session[t]){session=d.session[t];for(int r=0;r<4;r++)cumulative[r]=total(r%2,r<2)/double(d.base);}
  int clock=d.clock[t],slot=slot_index(clock);
  // No fabricated initialization for the three received expiry-only cycles.
  if(!initialized&&d.phase[0]==0&&clock==556&&!d.phase[t]){
   double spot=d.feature[t*8];if(good(spot)){
    for(int right=0;right<2;right++){int s=atm(t,right);int distance=d.u==0?2000:(d.expiry>=20260916?2000:4000);
     int k=int(floor(spot/d.step+.5))*d.step+(right? -distance:distance);int wing=find(k,right);
     if(s>=0)target[s]-=3*d.base;if(wing>=0)target[wing]+=3*d.base;
    }initialized=true;reason|=1;for(int r=0;r<4;r++)cumulative[r]=3;
   }
  }
  int deadline=d.expiry<20260803?927:914;
  if(d.phase[t]&&clock>=deadline){fill(target.begin(),target.end(),0);locked=true;reason|=16;}
  if(initialized&&!locked){
   if(risk==1)for(int j=0;j<d.C;j++)if(target[j]<0&&confirmed[j]<0&&good(cost[j])&&good(d.prior[t*d.C+j])&&d.prior[t*d.C+j]>=1.5*cost[j]){
    int right=d.right[j],before=total(right,true),removed=-target[j];target[j]=0;
    int wing=before?int(round(total(right,false)*removed/double(before)/d.base))*d.base:0;reduce_longs(right,wing);blocked[right]=t;reason|=2;
   }
   if(risk==2)for(int right=0;right<2;right++){
    double equity=realized[right];bool valid=true;int gross=0;
    for(int j=0;j<d.C;j++)if(d.right[j]==right&&confirmed[j]){gross+=abs(confirmed[j]);if(!good(d.prior[t*d.C+j]))valid=false;else equity+=confirmed[j]*(d.prior[t*d.C+j]-cost[j]);}
    if(side_locked[right]&&slot>0&&gross==0){side_locked[right]=false;episode[right]=equity;}
    if(!side_locked[right]&&total(right,true)>0&&valid&&equity-episode[right]<=-100000){
     for(int j=0;j<d.C;j++)if(d.right[j]==right)target[j]=0;side_locked[right]=true;blocked[right]=t;reason|=2;
    }
   }
   if((slot>0||(slot==0&&d.phase[t]))&&(!d.phase[t]||total(0,true)+total(1,true)>0)){
    for(int right=0;right<2;right++){
     if(blocked[right]==t||side_locked[right])continue;int s=atm(t,right);int w=budgetwing(t,s);if(s<0||w<0)continue;
     double shorts=allocation==0?1:cal.pool[d.u][d.phase[t]][slot][right];double longs=allocation==0?1:cal.pool[d.u][d.phase[t]][slot][right+2];
     if(allocation>=2){cumulative[right]+=shorts;cumulative[right+2]+=longs;
      double cap=allocation==3?cal.cap[d.u][0]:INFINITY;
      shorts=max(0.,min(cumulative[right],cap)-total(right,true)/double(d.base));
      longs=max(0.,(allocation==3?min(cumulative[right+2],cap):cumulative[right+2])-total(right,false)/double(d.base));
     }
     target[s]-=int(round(shorts))*d.base;target[w]+=int(round(longs))*d.base;reason|=1;
    }
   }
   if(!d.phase[t]&&clock>=910){
    for(int right=0;right<2;right++){
     int deficit=total(right,true)-total(right,false);if(deficit>0){int s=atm(t,right),w=budgetwing(t,s);if(w>=0){target[w]+=deficit;reason|=64;}}
     if(clock>=920){int sh=0,lo=0;for(int j=0;j<d.C;j++)if(d.right[j]==right){sh+=max(-confirmed[j],0);lo+=max(confirmed[j],0);}
      if(sh>lo){int amount=max(total(right,true)-lo,0);if(amount){reduce_shorts(right,amount);reason|=64;}}
     }
    }
   }
  }
  bool changed=previous!=target;if(changed)version++;return changed;
 }
};
